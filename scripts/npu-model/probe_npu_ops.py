#!/usr/bin/env python3
"""Probe individual ops on the Zhouyi NPU for *correctness*, not just support.

The op-support notes in `docs/local-ai.md` answer a different question: does the
graph compile and stay on the device. This asks whether the answer it computes
is right, which turns out to be independent -- a graph can be placed entirely on
the NPU, run at full speed, and return numbers that have nothing to do with the
model.

Each case is built as a tiny graph, placed with `session.disable_cpu_ep_fallback`
so a fallback is a hard error, then run against the CPU provider on identical
input. Three outcomes matter and they are all different:

* not placed        -- the op is genuinely unsupported
* placed, matches   -- usable
* placed, differs   -- the dangerous one, and the reason this script exists

Run it ON the board, from the detector's Python 3.11 environment, in a directory
holding the ./operator symlink:

    cd ~/smart_home_AI/deploy/npu
    ~/npu-venv/bin/python ~/smart_home_AI/scripts/npu-model/probe_npu_ops.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

SHAPE = [1, 8, 16, 16]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tolerance", type=float, default=1e-4)
    ap.add_argument("--workdir", type=Path, default=Path.home() / "smart_home_AI" / "deploy" / "npu")
    args = ap.parse_args()

    import os

    operator = args.workdir / "operator"
    if not operator.exists():
        print(f"no layer library at {operator}")
        return 1
    os.chdir(args.workdir)

    import numpy as np
    import onnxruntime as ort
    from onnx import TensorProto, helper, numpy_helper

    def const(name: str, value: float):
        return numpy_helper.from_array(np.array([value], dtype=np.float32), name)

    def const_channels(name: str, value: float):
        # (1, C, 1, 1): the shape a per-channel PReLU slope takes.
        return numpy_helper.from_array(np.full((1, SHAPE[1], 1, 1), value, dtype=np.float32), name)

    def build(nodes, inits, inputs=("x",)):
        graph = helper.make_graph(
            nodes, "probe",
            [helper.make_tensor_value_info(i, TensorProto.FLOAT, SHAPE) for i in inputs],
            [helper.make_tensor_value_info("y", TensorProto.FLOAT, SHAPE)],
            initializer=list(inits),
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
        model.ir_version = 8  # what this runtime accepts
        return model

    cases: dict[str, tuple] = {
        "relu": (build([helper.make_node("Relu", ["x"], ["y"])], []), ("x",)),
        "sigmoid": (build([helper.make_node("Sigmoid", ["x"], ["y"])], []), ("x",)),
        "mul_tensor": (build([helper.make_node("Mul", ["x", "z"], ["y"])], [], ("x", "z")), ("x", "z")),
        "mul_scalar_const": (build([helper.make_node("Mul", ["x", "c"], ["y"])], [const("c", -1.0)]), ("x",)),
        "mul_channel_const": (build([helper.make_node("Mul", ["x", "c"], ["y"])],
                                    [const_channels("c", 0.25)]), ("x",)),
        "sub_tensor": (build([helper.make_node("Sub", ["x", "z"], ["y"])], [], ("x", "z")), ("x", "z")),
        "sub_scalar_const": (build([helper.make_node("Sub", ["c", "x"], ["y"])], [const("c", 0.0)]), ("x",)),
        "add_tensor": (build([helper.make_node("Add", ["x", "z"], ["y"])], [], ("x", "z")), ("x", "z")),
        # The composed shape the model actually uses.
        "prelu_decomposed": (build([
            helper.make_node("Relu", ["x"], ["pos"]),
            helper.make_node("Mul", ["x", "neg"], ["negx"]),
            helper.make_node("Relu", ["negx"], ["negpart"]),
            helper.make_node("Mul", ["s", "negpart"], ["scaled"]),
            helper.make_node("Sub", ["pos", "scaled"], ["y"]),
        ], [const("neg", -1.0), const("s", 0.25)]), ("x",)),
        # For contrast: the activation that crashes the provider outright.
        "silu_shared_source": (build([
            helper.make_node("Sigmoid", ["x"], ["sg"]),
            helper.make_node("Mul", ["x", "sg"], ["y"]),
        ], []), ("x",)),
    }

    rng = np.random.default_rng(0)
    feeds = {n: rng.uniform(-3.0, 3.0, size=SHAPE).astype(np.float32) for n in ("x", "z")}

    print(f"{'case':<22} {'placed':<8} {'max abs diff':>14}  verdict")
    verdicts: dict[str, str] = {}
    for tag, (model, names) in cases.items():
        if tag == "silu_shared_source":
            print(f"{tag:<22} {'skipped':<8} {'-':>14}  known to crash the provider and deadlock; not run")
            verdicts[tag] = "skipped"
            continue

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        opts.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        try:
            npu = ort.InferenceSession(model.SerializeToString(), opts,
                                       providers=["ZhouyiExecutionProvider"])
        except Exception as exc:
            first = str(exc).splitlines()[0][:60]
            print(f"{tag:<22} {'NO':<8} {'-':>14}  unsupported: {first}")
            verdicts[tag] = "unsupported"
            continue

        cpu_opts = ort.SessionOptions()
        cpu_opts.log_severity_level = 3
        cpu = ort.InferenceSession(model.SerializeToString(), cpu_opts, providers=["CPUExecutionProvider"])

        feed = {n: feeds[n] for n in names}
        on_npu = npu.run(None, feed)[0].astype(np.float64)
        on_cpu = cpu.run(None, feed)[0].astype(np.float64)
        diff = float(np.max(np.abs(on_npu - on_cpu)))
        ok = diff < args.tolerance
        verdicts[tag] = "match" if ok else "MISCOMPUTED"
        print(f"{tag:<22} {'yes':<8} {diff:>14.6f}  {'match' if ok else '*** MISCOMPUTED ***'}")

    bad = [t for t, v in verdicts.items() if v == "MISCOMPUTED"]
    if bad:
        print(f"\nplaced on the NPU but computing the wrong answer: {bad}")
        print("An op in this list cannot be used, even though the graph compiles and runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
