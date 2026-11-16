"""The in-process engine's CPU adjustments (needs the OCR environment: pip install -e ".[ocr]"; skipped otherwise)."""
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from ferrero.ocr import local  # noqa: E402


def test_int8_experts_stay_within_a_percent_of_bfloat16():
    torch.manual_seed(0)
    linear = torch.nn.Linear(1280, 896, bias=False).to(torch.bfloat16)
    q = local._Int8Linear(linear)
    assert q.qweight.dtype == torch.int8 and q.qweight.element_size() * q.qweight.numel() == 896 * 1280
    for rows in (1, 40):
        x = torch.randn(rows, 1280, dtype=torch.bfloat16)
        exact = x.float() @ linear.weight.float().T
        err = (q(x).float() - exact).norm() / exact.norm()
        assert q(x).dtype == torch.bfloat16 and err < 0.015


def test_float32_products_match_bfloat16_ones():
    torch.manual_seed(1)
    linear = torch.nn.Linear(1280, 896).to(torch.bfloat16)
    x = torch.randn(64, 1280, dtype=torch.bfloat16)
    import types

    fast = types.MethodType(local._linear, linear)
    exact = x.float() @ linear.weight.float().T + linear.bias.float()
    assert (fast(x).float() - exact).norm() / exact.norm() < 0.005  # computed in float32, rounded once
    one = x[:1]
    assert torch.equal(fast(one), torch.nn.functional.linear(one, linear.weight, linear.bias))  # decode path unchanged


def test_confidence_leaves_out_layout_markup():
    engine = local.UnlimitedOcrLocal.__new__(local.UnlimitedOcrLocal)
    engine._layout_ids = ({10}, {11})  # <|det|>, <|/det|>
    engine._special_ids = {1}
    steps = [([10], [0.99]), ([50, 51], [0.4, 0.3]), ([11], [0.99]), ([60], [0.9]), ([61, 62], [0.6, 0.3]), ([1], [0.99])]
    tokens = [10, 50, 11, 60, 62, 1]  # label/box token 50 skipped; 60 at 0.9, 62 (second choice) at 0.3; EOS skipped
    confidence, counted = engine._confidence(tokens, steps)
    assert counted == 2 and confidence == pytest.approx((0.9 * 0.3) ** 0.5, abs=1e-4)  # geometric mean


def test_missing_triton_only_is_tolerated(monkeypatch, tmp_path):
    from transformers import dynamic_module_utils as dmu

    module = tmp_path / "modeling_x.py"
    module.write_text("import triton\nfrom .helper import x\n")
    monkeypatch.setattr(dmu, "check_imports", dmu.check_imports)  # restore after the test
    local._triton_is_optional()
    assert dmu.check_imports(str(module)) == ["helper"]
    module.write_text("import triton\nimport not_a_real_package_xyz\n")
    with pytest.raises(ImportError):
        dmu.check_imports(str(module))
