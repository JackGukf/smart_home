"""The NPU detection model pipeline.

These scripts exist because the previous model was lost: the training, export
and quantisation lived only in ~/npu-test/ on the board, and the 2026-09-03
reflash took them with it.  The backups were config-only and never held them.

The tests that matter here are the ones covering claims that are expensive to
re-derive and silent when wrong -- above all that the PReLU rewrite is an
identity, since a subtly wrong rewrite produces a model that runs and detects
slightly worse, which is exactly the kind of fault nobody notices.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "npu-model"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prelu_decomposition_is_numerically_exact() -> None:
    """PRelu(x, s) == Relu(x) - s * Relu(-x), and this must be exact.

    The NPU implements none of PRelu, LeakyRelu, Clip, Elu or HardSigmoid, so
    the activation has to be expressed in Relu/Mul/Sub or the model cannot run
    at all.  The identity holds in IEEE-754 because negation is exact, which is
    why the export asserts a difference of 0 rather than a tolerance.
    """
    onnx = pytest.importorskip("onnx")
    ort = pytest.importorskip("onnxruntime")
    np = pytest.importorskip("numpy")
    from onnx import TensorProto, helper, numpy_helper

    rewrite = load("export_rewrite")

    slope = numpy_helper.from_array(np.array([0.17], dtype=np.float32), "slope")
    graph = helper.make_graph(
        [helper.make_node("PRelu", ["x", "slope"], ["y"], name="act")],
        "prelu",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 8, 8])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 3, 8, 8])],
        initializer=[slope],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
    # onnx's helper defaults to a newer IR version than onnxruntime accepts;
    # ultralytics' exporter emits an older one, so this only bites hand-built
    # graphs like this test's.
    model.ir_version = min(model.ir_version, 10)
    onnx.checker.check_model(model)

    original = onnx.load_model_from_string(model.SerializeToString())

    assert rewrite.decompose_prelu(model) == 1
    onnx.checker.check_model(model)
    assert all(node.op_type != "PRelu" for node in model.graph.node)
    # Neg is unsupported too, so the negation must be a multiply.
    assert all(node.op_type != "Neg" for node in model.graph.node)

    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    a = ort.InferenceSession(original.SerializeToString(), opts, providers=["CPUExecutionProvider"])
    b = ort.InferenceSession(model.SerializeToString(), opts, providers=["CPUExecutionProvider"])

    rng = np.random.default_rng(0)
    # Spans both sides of zero: the negative half is the only part the rewrite
    # touches, and a rewrite that only handled positives would still pass on
    # inputs drawn from [0, 1].
    x = rng.uniform(-4.0, 4.0, size=(1, 3, 8, 8)).astype(np.float32)
    ya = a.run(None, {"x": x})[0]
    yb = b.run(None, {"x": x})[0]
    assert float(np.max(np.abs(ya - yb))) == 0.0, "the rewrite is not bit-exact"
    assert float(np.min(ya)) < 0.0, "test input never exercised the negative branch"


def test_silu_pattern_is_detected_because_it_crashes_the_device() -> None:
    """Mul(x, Sigmoid(x)) with a shared source is what kills the provider.

    It does not raise a Python error -- it fails with free(): invalid pointer
    inside the execution provider and then deadlocks every thread, so it has to
    be caught before the graph ever reaches the board.  Sigmoid alone passes and
    Mul alone passes; only the shared source is fatal.
    """
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    rewrite = load("export_rewrite")

    def build(mul_inputs: list[str]):
        graph = helper.make_graph(
            [
                helper.make_node("Sigmoid", ["x"], ["s"], name="sig"),
                helper.make_node("Mul", mul_inputs, ["y"], name="mul"),
            ],
            "g",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 2]),
             helper.make_tensor_value_info("other", TensorProto.FLOAT, [1, 2])],
            [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])],
        )
        built = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
        built.ir_version = min(built.ir_version, 10)
        return built

    assert rewrite.find_silu(build(["x", "s"])) == ["mul"], "shared-source SiLU not detected"
    # Mul(Sigmoid(a), b) with independent inputs was measured to pass on the
    # device, so flagging it would reject working graphs.
    assert rewrite.find_silu(build(["other", "s"])) == []


def test_calibration_uses_the_deployed_preprocessing() -> None:
    """Calibration ranges describe whatever distribution you feed the model.

    A calibration pipeline that drifts from the deployed one mis-scales every
    tensor, and the model still runs -- it is just quietly worse. Importing the
    detector's own to_input makes the two impossible to separate.
    """
    source = (SCRIPT_DIR / "quantize.py").read_text(encoding="utf-8")

    assert "from src.python.npu_detector import to_input" in source
    assert "QuantFormat.QDQ" in source, "the NPU runs QDQ models only"
    # Conv-only is the default because person AP is what a camera needs.
    assert '"Conv"' in source


def test_evaluation_scores_every_model_through_one_path() -> None:
    """A comparison is only meaningful if the models differ and nothing else does.

    The previous split lived on the board and is gone, so old numbers cannot be
    reproduced -- every model in a table has to be re-scored here, including
    stock, which means .pt inputs go through the same ONNX inference as ours.
    """
    source = (SCRIPT_DIR / "evaluate.py").read_text(encoding="utf-8")

    assert "def as_onnx" in source, ".pt models must be exported, not scored separately"
    assert "from src.python.npu_detector import COCO_NAMES, nms, to_input" in source
    assert "person_AP50" in source


def test_the_subset_split_is_reproducible_from_a_seed() -> None:
    """The reason the previous numbers are unusable is that its split was not.

    A split regenerated from a seed can be rebuilt on any machine, which is what
    makes a future model comparable to this one.
    """
    source = (SCRIPT_DIR / "fetch_coco_subset.py").read_text(encoding="utf-8")

    assert "random.Random(seed)" in source, "the split is not deterministic"
    assert "--seed" in source
