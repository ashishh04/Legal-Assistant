"""Command line for text recognition: ``python -m ferrero.ocr``.

    python -m ferrero.ocr                 recognise every scan in the document folder that is not recognised yet
    python -m ferrero.ocr --file NAME     only these files (repeatable)
    python -m ferrero.ocr status          what has been recognised, with confidence and time
    python -m ferrero.ocr stop            ask a running recognition to stop after its current page
    python -m ferrero.ocr download        fetch the Unlimited-OCR-2 model (pinned revision) into models/

Each page is saved as soon as it is read, so the run can be stopped (Ctrl+C, or ``stop``) and started again at any
time. After each document the document sync runs, so recognised scans become searchable one by one. Only one run
at a time: the model needs most of a laptop's memory.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import logging
import os
import sys
import time
from pathlib import Path

from pypdf import PdfReader

from ..config import get_settings
from ..sync.extract import MIN_TEXT_CHARS_PER_PAGE
from .reader import Stopped, recognize_pdf
from .results import OcrCache

MODEL_REPO = "baidu/Unlimited-OCR-2"
MODEL_REVISION = "0480966938291445591f69f08a13b041c073a96a"  # 2 Nov 2026; checked and tested with this code
MODEL_FILES = ["*.py", "*.json", "*.safetensors", "README.md"]


def is_scan(data: bytes) -> tuple[bool, str]:
    """(needs recognition, why not). Password-protected files are never opened, so never recognised."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            return False, "password-protected"
        chars = sum(len((p.extract_text() or "").strip()) for p in reader.pages)
    except Exception:
        return (False, "password-protected") if b"/Encrypt" in data else (False, "unreadable")
    if chars >= MIN_TEXT_CHARS_PER_PAGE * max(1, len(reader.pages)):
        return False, "has a text layer"
    return True, ""


class _Console(io.TextIOBase):
    """stdout without the model code's diagnostic prints ("[debug …]", "[PageRope …]"), copied to a log file."""

    _NOISE = ("[debug", "[Page", "[ImageMask", "[DASH", "[SparseAttn", "[TPS", "[Dash", "[dash")

    def __init__(self, target, log_path: Path | None):
        self._target, self._pending = target, ""
        self._log = open(log_path, "a", encoding="utf-8") if log_path else None

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:
        self._pending += s
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            if line.lstrip().startswith(self._NOISE):
                continue
            self._target.write(line + "\n")
            if self._log:
                self._log.write(f"{time.strftime('%H:%M:%S')} {line}\n")
        self.flush()
        return len(s)

    def flush(self) -> None:
        self._target.flush()
        if self._log:
            self._log.flush()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":  # never os.kill on Windows: any signal there terminates the process
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class _RunLock:
    """data/ocr/.running holds the PID of the run in progress; data/ocr/.stop asks it to stop."""

    def __init__(self, folder: Path):
        self.lock, self.stop_file = folder / ".running", folder / ".stop"

    def holder(self) -> int | None:
        try:
            pid = int(self.lock.read_text().strip() or 0)
        except (OSError, ValueError):
            return None
        return pid if _pid_alive(pid) else None

    def acquire(self) -> bool:
        if self.holder() is not None:
            return False
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        self.lock.write_text(str(os.getpid()))
        self.stop_file.unlink(missing_ok=True)
        return True

    def release(self) -> None:
        if self.holder() == os.getpid():
            self.lock.unlink(missing_ok=True)
        self.stop_file.unlink(missing_ok=True)

    def stop_requested(self) -> bool:
        return self.stop_file.exists()


def _lower_priority() -> None:
    """Run below normal priority, so the machine stays responsive while a long recognition run is going."""
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
        else:
            os.nice(10)
    except Exception:
        pass


def _fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m" if seconds >= 3600 else f"{seconds // 60}m{seconds % 60:02d}s"


def cmd_run(args) -> int:
    settings = get_settings()
    sys.stdout = _Console(sys.stdout, args.log)
    folder = args.path or settings.documents_dir
    cache = OcrCache(settings.ocr_dir)
    pdfs = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    if args.file:
        wanted = {n.lower() for n in args.file}
        pdfs = [p for p in pdfs if p.name.lower() in wanted]
        if not pdfs:
            print(f"None of {', '.join(args.file)} is in {folder}")
            return 2

    todo: list[tuple[Path, bytes, str, int]] = []
    already = 0
    for path in pdfs:
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        scan, _ = is_scan(data)
        if not scan:
            continue
        if cache.get(sha) is not None and not args.redo:
            already += 1
            continue
        if any(t[2] == sha for t in todo):  # an identical copy is recognised once
            continue
        todo.append((path, data, sha, len(PdfReader(io.BytesIO(data)).pages)))
    todo.sort(key=lambda t: (t[3], t[0].name.lower()))  # shortest first: the most documents searchable soonest
    if args.limit:
        todo = todo[:args.limit]
    pages_total = sum(t[3] for t in todo)
    print(f"{len(todo)} scans to recognise ({pages_total} pages); {already} already recognised. Cache: {cache.folder}")
    if not todo:
        return 0
    lock = _RunLock(cache.folder)
    if not lock.acquire():
        print(f"Text recognition is already running (process {lock.holder()}). Stop it with: python -m ferrero.ocr stop")
        return 3
    try:
        return _run(args, settings, cache, todo, pages_total, lock)
    finally:
        lock.release()


def _run(args, settings, cache: OcrCache, todo, pages_total: int, lock: _RunLock) -> int:
    from .engines import make_engine

    options = {k: v for k, v in (("threads", args.threads), ("mode", args.mode), ("decode_threads", args.decode_threads),
                                 ("experts", args.experts)) if v}
    engine = make_engine(settings, args.engine, **options)  # options apply to the local engine only
    if not args.normal_priority:
        _lower_priority()
    if hasattr(engine, "load"):
        started = time.perf_counter()
        engine.load()
        print(f"Model loaded in {time.perf_counter() - started:.0f} s on {getattr(engine, 'device', '?')}"
              f"{f', routed experts: {engine.experts}' if getattr(engine, 'device', '') == 'cpu' else ''}")
    print(f"Engine: {engine.engine} ({engine.model}, {engine.mode})")

    sync = _Syncer(settings, args.path or settings.documents_dir, full=args.redo) if not args.no_sync else None
    done_pages, spent = 0, 0.0
    try:
        for i, (path, data, sha, n_pages) in enumerate(todo, start=1):
            if args.redo:
                cache.remove(sha)
            print(f"[{i}/{len(todo)}] {path.name} – {n_pages} page{'s' * (n_pages != 1)}", flush=True)

            def progress(number, total, page):
                nonlocal done_pages, spent
                done_pages += 1
                spent += page.seconds
                left = (pages_total - done_pages) * spent / done_pages
                conf = f"{page.score:.0%}" if page.score is not None else "n/a"
                rate = page.tokens / max(page.seconds - page.prefill_seconds, 1e-6)
                print(f"    page {number}/{total}: {page.tokens} tokens in {_fmt_time(page.seconds)} (reading the image "
                      f"{_fmt_time(page.prefill_seconds)}, then {rate:.1f} tokens/s), confidence {conf}"
                      f"{'' if page.finish == 'stop' else ' (hit the token limit)'} · about {_fmt_time(left)} left", flush=True)

            try:
                result = recognize_pdf(engine, data, sha, path.name, cache, progress, should_stop=lock.stop_requested)
            except Stopped:
                raise
            except Exception as e:  # one bad file must not stop the run
                logging.getLogger(__name__).exception("Recognition failed for %s", path.name)
                print(f"    failed: {type(e).__name__}: {e}")
                continue
            print(f"    done: confidence {result.confidence:.0%}" if result.confidence is not None else "    done")
            if sync is not None:
                sync.dirty = True
                sync.run()
            if lock.stop_requested():
                raise Stopped(path.name)
    except (KeyboardInterrupt, Stopped):
        print("\nStopped. Finished pages are saved; run the same command again to continue.")
        return 130
    finally:
        if sync is not None:
            sync.run(final=True)
    return 0


class _Syncer:
    """Runs the incremental document sync, so each recognised scan becomes searchable straight away."""

    def __init__(self, settings, folder: Path, full: bool = False):
        self.full = full  # re-recognised scans have unchanged files: only a full pass re-indexes them
        from ..casemodel import CaseModel
        from ..sync.cli import build_source
        from ..sync.index import DocumentIndex
        from ..sync.sources import load_manifest, manifest_next_to
        from .reader import OcrReader

        self.settings = settings
        self.model = CaseModel(settings.csv_dir, settings.today, catalogue=settings.catalogue_path)
        self.index = DocumentIndex(settings.index_path)
        manifest_path = manifest_next_to(folder)
        manifest = load_manifest(manifest_path) if manifest_path else None
        self.source = build_source("local", folder, self.model, manifest)
        # The cache only: this process already holds the model, and the sync must never load a second one.
        self.reader = OcrReader(OcrCache(settings.ocr_dir), None, min_confidence=settings.ocr_min_confidence,
                                review_confidence=settings.ocr_review_confidence)
        self.dirty = False

    def run(self, final: bool = False) -> None:
        from ..sync.runner import run_sync

        if final and not self.dirty:
            return
        result = run_sync(self.source, self.index, self.model, ocr=self.reader, full=self.full,
                          status_csv=self.settings.data_dir / "sync_status.csv")
        self.dirty = False
        stats = self.index.stats()
        print(f"    index: {stats['indexed']} searchable documents, {stats['passages']} passages"
              f" ({result.recognised} recognised scans indexed this run, {len(result.awaiting_ocr)} still waiting)", flush=True)


def cmd_status(args) -> int:
    settings = get_settings()
    cache = OcrCache(settings.ocr_dir)
    results = list(cache)
    if not results:
        print(f"Nothing recognised yet ({cache.folder}). Run: python -m ferrero.ocr")
        return 0
    pages = sum(len(r.pages) for r in results)
    seconds = sum(r.seconds for r in results)
    print(f"{len(results)} scans recognised, {pages} pages, {_fmt_time(seconds)} of recognition ({cache.folder})")
    for r in sorted(results, key=lambda r: (r.confidence or 0)):
        per_page = ", ".join(f"{p.score:.0%}" if p.score is not None else "n/a" for p in r.pages)
        print(f"  {r.confidence or 0:5.0%}  [{per_page}]  {r.file_name}")
    return 0


def cmd_stop(args) -> int:
    lock = _RunLock(get_settings().ocr_dir)
    pid = lock.holder()
    if pid is None:
        print("No text recognition is running.")
        return 0
    lock.stop_file.write_text("stop")
    print(f"Asked the recognition run (process {pid}) to stop after its current page; finished pages are kept.")
    return 0


def cmd_download(args) -> int:
    settings = get_settings()
    target = args.to or settings.ocr_model_dir
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit('Downloading needs the OCR environment: pip install -e ".[ocr]"') from None
    print(f"Downloading {MODEL_REPO}@{MODEL_REVISION[:7]} (about 6.7 GB) to {target}")
    snapshot_download(MODEL_REPO, revision=MODEL_REVISION, local_dir=target, allow_patterns=MODEL_FILES)
    (Path(target) / "REVISION").write_text(MODEL_REVISION + "\n")
    print("Done.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ferrero-ocr", description="Recognise the text of scanned case documents.")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="recognise scans (the default)")
    for p in (parser, run):
        p.add_argument("--path", type=Path, help="document folder (default: the corpus the sync uses)")
        p.add_argument("--file", action="append", help="only this file name (repeatable)")
        p.add_argument("--limit", type=int, help="at most this many scans")
        p.add_argument("--engine", choices=("local", "server"), help="default: FERRERO_OCR_ENGINE (server if FERRERO_OCR_URL)")
        p.add_argument("--mode", choices=("gundam", "base"), help="local engine: page plus detail tiles (default) or page only")
        p.add_argument("--threads", type=int, help="local engine: CPU threads for the prompt and vision encoder")
        p.add_argument("--decode-threads", type=int, help="local engine: CPU threads while writing text (default: same)")
        p.add_argument("--experts", choices=("auto", "ram", "mapped", "int8"),
                       help="local engine on a CPU: keep the routed experts in RAM, read them from the model files "
                            "(mapped), or as int8 (half the memory). Default: FERRERO_OCR_EXPERTS, auto by free memory")
        p.add_argument("--normal-priority", action="store_true", help="do not lower this process's priority")
        p.add_argument("--log", type=Path, help="also append the progress lines to this file")
        p.add_argument("--redo", action="store_true", help="recognise again even if already recognised")
        p.add_argument("--no-sync", action="store_true", help="do not run the document sync after each document")
    sub.add_parser("status", help="what has been recognised")
    sub.add_parser("stop", help="ask a running recognition to stop after its current page")
    dl = sub.add_parser("download", help="fetch the model")
    dl.add_argument("--to", type=Path, help="target folder (default: models/Unlimited-OCR-2)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "stop":
        return cmd_stop(args)
    if args.command == "download":
        return cmd_download(args)
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
