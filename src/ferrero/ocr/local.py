"""Baidu's Unlimited-OCR-2 (https://github.com/baidu/Unlimited-OCR), run in this process with Transformers.

Needs the OCR environment (``pip install -e ".[ocr]"``) and the model folder (``python -m ferrero.ocr download``).
It uses an NVIDIA GPU when there is one and the CPU otherwise. Baidu's code targets CUDA. On a CPU it runs
unchanged (its files are not edited) with three adjustments made here at run time:

* Baidu's Triton kernels (CUDA only, never called on a CPU) are imported only so that Transformers copies them.
  Transformers' import check is told that a missing ``triton`` is fine; the kernels' own import then fails inside
  Baidu's ``try/except``, exactly as on any machine without Triton.
* Two ``.cuda()`` calls in the image path become no-ops when there is no GPU.
* On CPUs without native bfloat16 arithmetic, large matrix products (the vision encoder and the prompt prefill) run
  in float32, which is about five times faster there. The weights stay bfloat16, and decoding one token at a time
  is unchanged.

Memory. The model holds 6.7 GB of weights, 4.8 GB of them in the 704 routed experts (64 per layer, 6 used per token).
When the machine cannot spare that much RAM, Windows pages the weights out and every token waits for the disk.
``experts`` chooses how the routed experts are held:

* ``"ram"``: as Transformers loads them (fastest when there is room);
* ``"mapped"``: read straight from the model files through a read-only memory map. The weights are bit-for-bit the
  same, and under memory pressure Windows drops and re-reads them from the files. Measured on a 16 GB laptop with
  little free memory: 1-2 tokens/s, against 0.4 tokens/s as loaded (the default when less than 8 GB is free);
* ``"int8"``: 8-bit with one scale per output channel (2.4 GB instead of 4.8 GB). Each product differs from bfloat16
  by about 0.8% (bfloat16's own rounding is about 0.2%). Turning the int8 weights back into floats for every token
  costs time: on that laptop it ran at 0.7 tokens/s, so it only pays off when memory is scarcer still.
"""
from __future__ import annotations

import gc
import io
import json
import os
import time
import types
from pathlib import Path

os.environ.setdefault("CODE_STAMP_LOG", "0")  # Baidu's code prints a code fingerprint on import otherwise
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # the model is loaded from its local folder, never fetched here

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

from .results import OcrPage, text_confidence  # noqa: E402

MODEL_ID = "baidu/Unlimited-OCR-2"
PROMPT = "Multi page parsing."  # the instruction the model was trained with ("<PAGE><image>" is added per page)
# Layout markup (block type, heading level and box): "<BLOCK>title<LEVEL1>[x1, y1, x2, y2]<FORK>", or DeepSeek-OCR's
# "<|det|>…<|/det|>". Confidence leaves it out: box coordinates are near-ties that say nothing about legibility.
_LAYOUT_TAGS = (("<BLOCK>", "<FORK>"), ("<|det|>", "<|/det|>"), ("<|ref|>", "<|/ref|>"))


def _triton_is_optional() -> None:
    """Let Transformers load Baidu's code without Triton (its kernels only run on CUDA, behind try/except)."""
    import importlib.util

    if importlib.util.find_spec("triton") is not None:
        return
    from transformers import dynamic_module_utils as dmu

    if getattr(dmu.check_imports, "_triton_optional", False):
        return
    original = dmu.check_imports

    def check_imports(filename):
        try:
            return original(filename)
        except ImportError as e:
            missing = str(e).split("environment:", 1)[-1].split(".", 1)[0]
            if [m.strip() for m in missing.split(",")] == ["triton"]:
                return dmu.get_relative_imports(filename)
            raise

    check_imports._triton_optional = True
    dmu.check_imports = check_imports


def _cuda_calls_are_no_ops() -> None:
    if not torch.cuda.is_available():
        torch.Tensor.cuda = lambda self, *args, **kwargs: self  # noqa: E731


def _linear(self: torch.nn.Linear, x: torch.Tensor) -> torch.Tensor:
    if x.dtype is torch.bfloat16 and x.numel() >= 16 * x.shape[-1]:  # a real matrix product, not one token
        bias = None if self.bias is None else self.bias.float()
        return F.linear(x.float(), self.weight.float(), bias).to(torch.bfloat16)
    return F.linear(x, self.weight, self.bias)


def _conv(self: torch.nn.Conv2d, x: torch.Tensor) -> torch.Tensor:
    if x.dtype is torch.bfloat16:
        bias = None if self.bias is None else self.bias.float()
        return self._conv_forward(x.float(), self.weight.float(), bias).to(torch.bfloat16)
    return self._conv_forward(x, self.weight, self.bias)


def _bf16_is_slow() -> bool:
    """True when this CPU multiplies bfloat16 matrices slower than float32 ones (no AVX512-BF16 / AMX)."""
    a, w = torch.randn(256, 1280, dtype=torch.bfloat16), torch.randn(896, 1280, dtype=torch.bfloat16)

    def timed(fn) -> float:
        fn()
        t = time.perf_counter()
        for _ in range(3):
            fn()
        return time.perf_counter() - t

    return timed(lambda: a @ w.T) > 1.5 * timed(lambda: (a.float() @ w.float().T).bfloat16())


_SCRATCH: dict[tuple[int, int], torch.Tensor] = {}


class _Int8Linear(torch.nn.Module):
    """A routed expert's linear layer with int8 weights and one float32 scale per output channel."""

    def __init__(self, linear: torch.nn.Linear):
        super().__init__()
        w = linear.weight.detach().float()
        scale = (w.abs().amax(dim=1) / 127).clamp(min=1e-12)
        self.register_buffer("qweight", torch.round(w / scale[:, None]).clamp(-127, 127).to(torch.int8))
        self.register_buffer("scale", scale)
        self.in_features, self.out_features = linear.in_features, linear.out_features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shape = tuple(self.qweight.shape)
        weight = _SCRATCH.get(shape)
        if weight is None:  # one reusable float32 buffer per shape: experts run one at a time
            weight = _SCRATCH[shape] = torch.empty(shape, dtype=torch.float32)
        weight.copy_(self.qweight)
        y = torch.mm(x.reshape(-1, self.in_features).float(), weight.T).mul_(self.scale)
        return y.to(x.dtype).reshape(*x.shape[:-1], self.out_features)


def _routed_expert_linears(model: torch.nn.Module):
    for name, module in model.named_modules():
        if ".mlp.experts." in name and isinstance(module, torch.nn.Linear):
            yield name, module


def _experts_to_int8(model: torch.nn.Module) -> int:
    count = 0
    for name, module in list(_routed_expert_linears(model)):
        parent_name, _, attr = name.rpartition(".")
        setattr(model.get_submodule(parent_name), attr, _Int8Linear(module))
        count += 1
    gc.collect()
    return count


class _MappedCheckpoint:
    """A .safetensors file mapped read-only. (safetensors' own loader maps files copy-on-write, which Windows charges
    in full against the commit limit; a read-only view costs nothing until pages are read, and pages can always be
    dropped and re-read from the file.)"""

    def __init__(self, path: Path):
        import mmap

        self._file = open(path, "rb")
        self._map = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        size = int.from_bytes(self._map[:8], "little")
        self._header = json.loads(self._map[8:8 + size])
        self._base = 8 + size

    def tensor(self, key: str) -> torch.Tensor:
        import warnings

        meta = self._header[key]
        if meta["dtype"] != "BF16":
            raise RuntimeError(f"{key} is {meta['dtype']}, expected BF16")
        start, end = meta["data_offsets"]
        with warnings.catch_warnings():  # read-only buffer: fine, weights are never written
            warnings.simplefilter("ignore")
            flat = torch.frombuffer(self._map, dtype=torch.bfloat16, count=(end - start) // 2, offset=self._base + start)
        return flat.view(meta["shape"])


def _map_experts(model: torch.nn.Module, model_dir: Path) -> list[_MappedCheckpoint]:
    """Point the routed experts' weights at the checkpoint files (memory-mapped, read-only, zero-copy)."""
    shards = json.loads((model_dir / "model.safetensors.index.json").read_text())["weight_map"]
    files: dict[str, _MappedCheckpoint] = {}
    for name, module in list(_routed_expert_linears(model)):
        key = f"{name}.weight"
        shard = shards.get(key)
        if shard is None:
            continue
        if shard not in files:
            files[shard] = _MappedCheckpoint(model_dir / shard)
        tensor = files[shard].tensor(key)
        if tensor.shape != module.weight.shape:
            raise RuntimeError(f"{key} in {shard} does not match the model")
        module._parameters["weight"] = torch.nn.Parameter(tensor, requires_grad=False)
    gc.collect()
    return list(files.values())  # the files must stay mapped while the model is in use


def available_memory_gb() -> float | None:
    """Physical memory the OS could hand out now (Windows: free + standby), in GB."""
    try:
        if os.name == "nt":
            import ctypes

            class _Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            status = _Status()
            status.dwLength = ctypes.sizeof(_Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullAvailPhys / 2**30
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
    except Exception:
        return None


class _TokenRecorder(torch.nn.Module):
    """Wraps the output head and records the five most likely tokens, with probabilities, at every step."""

    def __init__(self, head: torch.nn.Module):
        super().__init__()
        self.head = head
        self.steps: list[tuple[list[int], list[float]]] = []
        self.on_first_step = None  # called once per page, when the prompt has been read (prefill done)

    @property
    def weight(self) -> torch.Tensor:  # Baidu's generate loop reads lm_head.weight.device
        return self.head.weight

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        logits = self.head(hidden)
        if not self.steps and self.on_first_step is not None:
            self.on_first_step()
        top = torch.topk(torch.softmax(logits[0, -1].float(), dim=-1), 5)
        self.steps.append((top.indices.tolist(), top.values.tolist()))
        return logits


class UnlimitedOcrLocal:
    engine = "Unlimited-OCR-2"

    def __init__(self, model_dir: Path, *, mode: str = "gundam", max_new_tokens: int = 4096,
                 threads: int | None = None, decode_threads: int | None = None, experts: str = "auto"):
        if mode not in ("gundam", "base"):
            raise ValueError("mode is 'gundam' (page plus detail tiles, the model's default) or 'base' (page only)")
        if experts not in ("auto", "ram", "mapped", "int8"):
            raise ValueError("experts is auto, ram, mapped or int8")
        self.model_dir = Path(model_dir)
        self.mode = mode
        self.max_new_tokens = max_new_tokens
        self.threads = threads
        self.decode_threads = decode_threads
        self.experts = experts
        self._model = self._tokenizer = self._recorder = None
        self._mapped_files: list = []
        self._layout_ids: tuple[set[int], set[int]] = (set(), set())
        self._special_ids: set[int] = set()
        self.device = "cpu"

    @property
    def model(self) -> str:
        rev = self.model_dir / "REVISION"
        label = f"{MODEL_ID}@{rev.read_text().strip()[:7]}" if rev.is_file() else MODEL_ID
        return f"{label} (int8 experts)" if self.experts == "int8" else label

    def check(self) -> None:
        """Raise a plain-language error when the model folder is incomplete."""
        missing = [n for n in ("config.json", "modeling_unlimitedocr.py", "tokenizer.json", "model.safetensors.index.json")
                   if not (self.model_dir / n).is_file()]
        if missing:
            raise FileNotFoundError(f"The Unlimited-OCR-2 model is not in {self.model_dir} (missing {', '.join(missing)}). "
                                    "Run: python -m ferrero.ocr download")

    def load(self) -> None:
        if self._model is not None:
            return
        self.check()
        from transformers import AutoModel, AutoTokenizer

        _triton_is_optional()
        _cuda_calls_are_no_ops()
        if self.threads:
            torch.set_num_threads(self.threads)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.experts == "auto":  # decided before loading, from the memory the machine can spare
            free = available_memory_gb()
            self.experts = "ram" if self.device == "cuda" or free is None or free > 8 else "mapped"
        tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), trust_remote_code=True)
        model = AutoModel.from_pretrained(str(self.model_dir), trust_remote_code=True, use_safetensors=True,
                                          torch_dtype=torch.bfloat16, low_cpu_mem_usage=True)
        model = model.eval().to(self.device)
        if self.device == "cpu" and self.experts == "mapped":
            self._mapped_files = _map_experts(model, self.model_dir)
        elif self.device == "cpu" and self.experts == "int8":
            _experts_to_int8(model)
        if self.device == "cpu" and _bf16_is_slow():
            for module in model.modules():
                if isinstance(module, torch.nn.Linear):
                    module.forward = types.MethodType(_linear, module)
                elif isinstance(module, torch.nn.Conv2d):
                    module.forward = types.MethodType(_conv, module)
        self._recorder = _TokenRecorder(model.lm_head)
        model.lm_head = self._recorder
        if self.decode_threads:
            prefill_threads = torch.get_num_threads()
            self._recorder.on_first_step = lambda: torch.set_num_threads(self.decode_threads)
            self._restore_threads = lambda: torch.set_num_threads(prefill_threads)
        self._model, self._tokenizer = model, tokenizer
        opening, closing = set(), set()
        for open_tag, close_tag in _LAYOUT_TAGS:
            for tag, bucket in ((open_tag, opening), (close_tag, closing)):
                tid = tokenizer.convert_tokens_to_ids(tag)
                if isinstance(tid, int) and tid != tokenizer.unk_token_id:
                    bucket.add(tid)
        self._layout_ids = (opening, closing)
        # Special and added tokens (<PAGE>, layout tags, end of text) are structure, not recognised text.
        self._special_ids = set(tokenizer.all_special_ids) | set(getattr(tokenizer, "added_tokens_decoder", {}) or {})

    def _text_token_probs(self, token_ids: list[int], steps: list[tuple[list[int], list[float]]]) -> list[float]:
        """The probability of each recognised-text token; layout markup (block labels and boxes) is left out."""
        opening, closing = self._layout_ids
        inside, probs = False, []
        for tid, (ids, ps) in zip(token_ids, steps):
            if tid in opening:
                inside = True
            elif tid in closing:
                inside = False
            elif not inside and tid not in self._special_ids:
                probs.append(ps[ids.index(tid)] if tid in ids else 0.0)
        return probs

    def _confidence(self, token_ids: list[int], steps: list[tuple[list[int], list[float]]]) -> tuple[float | None, int]:
        """Confidence of the recognised text (see results.text_confidence), and how many text tokens there were."""
        probs = self._text_token_probs(token_ids, steps)
        return text_confidence(probs), len(probs)

    def recognize_page(self, image: bytes, number: int = 1) -> OcrPage:
        self.load()
        picture = ImageOps.exif_transpose(Image.open(io.BytesIO(image))).convert("RGB")
        self._recorder.steps.clear()
        if self.decode_threads:
            self._restore_threads()
        started = time.perf_counter()
        result = self._model.infer(self._tokenizer, prompt=PROMPT, image_file=picture,
                                   crop_mode=None if self.mode == "gundam" else False, eval_mode=True,
                                   return_dict=True, max_new_tokens=self.max_new_tokens)
        ids = result["token_ids"]
        probs = self._text_token_probs(ids, self._recorder.steps)
        return OcrPage(number=number, text=result["text"], confidence=text_confidence(probs), tokens=len(ids),
                       finish=result["finish_reason"], seconds=round(time.perf_counter() - started, 1),
                       prefill_seconds=round(result.get("prefill_time") or 0.0, 1),
                       text_token_probs=[round(p, 3) for p in probs])
