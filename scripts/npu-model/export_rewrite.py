#!/usr/bin/env python3
"""Export the finetuned model to ONNX and rewrite PReLU into ops the NPU has.

The Zhouyi execution provider does not implement PRelu -- and it does not
implement LeakyRelu, Clip, Elu, HardSigmoid or Neg either.  It does implement
Relu, Mul and Sub, and PReLU decomposes into exactly those:

    PRelu(x, s)  ==  Relu(x) - s * Relu(-x)

which is an identity, not an approximation: ``Relu(x) = max(0, x)`` and
``Relu(-x) = -min(0, x)``, so the right-hand side is ``max(0,x) + s*min(0,x)``,
the definition of PReLU.  Negation is exact in IEEE-754, so the rewritten graph
is bit-identical, and this script asserts that rather than trusting it.

``Neg`` is unsupported, so the negation is ``Mul(x, -1.0)``.

Also audits the finished graph for the two things that kill this device:
unsupported activations, and the SiLU pattern ``Mul(x, Sigmoid(x))`` -- shared
source, which crashes the provider with ``free(): invalid pointer`` and then
deadlocks every thread.  Sigmoid alone is fine; Mul alone is fine.

    python3 scripts/npu-model/export_rewrite.py --weights ~/npu-training/runs/prelu/weights/best.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

# Measured on the board with session.disable_cpu_ep_fallback=1, which turns a
# silent CPU fallback into a hard error. Anything outside this list has not been
# proven and may simply run on the CPU while looking like it ran on the NPU.
KNOWN_UNSUPPORTED = {"PRelu", "LeakyRelu", "Clip", "Elu", "HardSigmoid", "Neg", "Relu6"}


def decompose_prelu(model: onnx.ModelProto) -> int:
    """Replace every PRelu node with Relu/Mul/Sub. Returns how many."""
    graph = model.graph
    minus_one = "prelu_rewrite_minus_one"
    if not any(init.name == minus_one for init in graph.initializer):
        graph.initializer.append(
            numpy_helper.from_array(np.array([-1.0], dtype=np.float32), minus_one)
        )

    rebuilt = []
    replaced = 0
    for node in graph.node:
        if node.op_type != "PRelu":
            rebuilt.append(node)
            continue

        x, slope = node.input[0], node.input[1]
        out = node.output[0]
        tag = f"prelu{replaced}"
        # Order matters: ONNX requires topologically sorted nodes, and inserting
        # the replacements where the original stood preserves that.
        rebuilt += [
            helper.make_node("Relu", [x], [f"{tag}_pos"], name=f"{tag}_pos"),
            helper.make_node("Mul", [x, minus_one], [f"{tag}_negx"], name=f"{tag}_negx"),
            helper.make_node("Relu", [f"{tag}_negx"], [f"{tag}_negpart"], name=f"{tag}_negpart"),
            helper.make_node("Mul", [slope, f"{tag}_negpart"], [f"{tag}_scaled"], name=f"{tag}_scaled"),
            helper.make_node("Sub", [f"{tag}_pos", f"{tag}_scaled"], [out], name=f"{tag}_sub"),
        ]
        replaced += 1

    del graph.node[:]
    graph.node.extend(rebuilt)
    return replaced


def find_silu(model: onnx.ModelProto) -> list[str]:
    """Mul(x, Sigmoid(x)) with a shared source -- the pattern that crashes the EP."""
    sigmoid_src = {n.output[0]: n.input[0] for n in model.graph.node if n.op_type == "Sigmoid"}
    hits = []
    for node in model.graph.node:
        if node.op_type != "Mul" or len(node.input) != 2:
            continue
        a, b = node.input
        if (a in sigmoid_src and sigmoid_src[a] == b) or (b in sigmoid_src and sigmoid_src[b] == a):
            hits.append(node.name or node.output[0])
    return hits


def audit(model: onnx.ModelProto) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in model.graph.node:
        counts[node.op_type] = counts.get(node.op_type, 0) + 1
    return dict(sorted(counts.items()))


def verify_equivalent(before: Path, after: Path, runs: int = 3) -> float:
    """Run both graphs on the same random inputs; return the worst difference."""
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    a = ort.InferenceSession(str(before), opts, providers=["CPUExecutionProvider"])
    b = ort.InferenceSession(str(after), opts, providers=["CPUExecutionProvider"])
    name_a = a.get_inputs()[0].name
    name_b = b.get_inputs()[0].name
    shape = [d if isinstance(d, int) else 1 for d in a.get_inputs()[0].shape]

    worst = 0.0
    rng = np.random.default_rng(0)
    for _ in range(runs):
        # Real preprocessing is letterbox/255, so inputs live in [0,1]; test there
        # plus the negative side the rewrite actually changes.
        x = rng.uniform(-0.5, 1.0, size=shape).astype(np.float32)
        ya = a.run(None, {name_a: x})[0]
        yb = b.run(None, {name_b: x})[0]
        worst = max(worst, float(np.max(np.abs(ya.astype(np.float64) - yb.astype(np.float64)))))
    return worst


def split_head(model: onnx.ModelProto, npz_path: Path) -> list[str] | None:
    """Cut the graph at the detection head, leaving only the body to be quantised.

    Everything after the last six convolutions is arithmetic on small tensors -
    a DFL softmax, an anchor add, a stride multiply - and it is where INT8 goes
    wrong.  A QDQ ``Concat`` gives all of its inputs one shared scale, so any
    Concat joining tensors of different magnitude destroys the smaller one, and
    this head has two of them:

    * ``Concat_3`` joins boxes (0-640) with class scores (0-1).  Quantised, one
      INT8 step is ~2.5 and **every class score in the model rounds to zero**.
    * ``Concat_2`` joins the box centre (grid units, up to ~80) with its size
      (usually under 20).  The size collapses and every box comes out with no
      height.

    Patching them one at a time is whack-a-mole - the head also holds a Softmax
    and a Div that INT8 serves badly.  Cutting the whole head off removes every
    instance at once, and costs nothing: the head is a rounding error of the
    model's compute next to 64 convolutions, and numpy does it exactly.

    The constants the head needs - anchor points, strides, DFL weights - are
    lifted out of this graph rather than recomputed, so the decode cannot drift
    from the model it decodes.  Returns the output names, body-order.
    """
    from onnx import numpy_helper

    convs: dict[str, str] = {}
    for node in model.graph.node:
        for branch in ("cv2", "cv3"):
            for scale in range(3):
                if node.name == f"/model.22/{branch}.{scale}/{branch}.{scale}.2/Conv":
                    convs[f"{branch}.{scale}"] = node.output[0]
    if len(convs) != 6:
        return None

    initializers = {i.name: numpy_helper.to_array(i) for i in model.graph.initializer}
    try:
        meta = {
            "anchors": initializers["/model.22/Constant_12_output_0"],
            "strides": initializers["/model.22/Constant_15_output_0"],
            "dfl": initializers["model.22.dfl.conv.weight"],
        }
    except KeyError:
        return None

    order = [convs[f"cv2.{i}"] for i in range(3)] + [convs[f"cv3.{i}"] for i in range(3)]
    keep = set(order)

    # Everything the kept outputs depend on, walked backwards. Anything else in
    # the graph is head-only and goes.
    producer = {out: n for n in model.graph.node for out in n.output}
    needed, stack = set(), list(order)
    while stack:
        name = stack.pop()
        node = producer.get(name)
        if node is None or id(node) in needed:
            continue
        needed.add(id(node))
        stack.extend(node.input)

    for node in [n for n in model.graph.node if id(n) not in needed]:
        model.graph.node.remove(node)

    inferred = onnx.shape_inference.infer_shapes(model)
    known = {v.name: v for v in inferred.graph.value_info}
    for stale in list(model.graph.output):
        model.graph.output.remove(stale)
    for name in order:
        if name not in known:
            return None
        model.graph.output.append(known[name])

    # Drop initializers nothing refers to any more, so the file does not carry
    # the head's weights it will never use.
    used = {i for n in model.graph.node for i in n.input}
    for init in [i for i in model.graph.initializer if i.name not in used]:
        model.graph.initializer.remove(init)

    np.savez(npz_path, **meta)
    return order


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", type=Path, required=True, help="finetuned .pt")
    ap.add_argument("--outdir", type=Path, default=Path.home() / "npu-training" / "export")
    ap.add_argument("--imgsz", type=int, default=640, help="must match the detector's letterbox size")
    ap.add_argument("--opset", type=int, default=12)
    ap.add_argument("--no-split-head", action="store_true",
                    help="quantise the detection head too. Only useful for reproducing the "
                         "failure it causes: its Concats force tensors of very different "
                         "magnitude to share one INT8 scale, and the smaller one is erased")
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO

    print(f"exporting {args.weights}")
    model = YOLO(str(args.weights))
    exported = Path(model.export(format="onnx", imgsz=args.imgsz, opset=args.opset,
                                 dynamic=False, simplify=True, nms=False, verbose=False))
    raw = args.outdir / "prelu_ft.onnx"
    raw.write_bytes(exported.read_bytes())
    print(f"  {raw}")

    graph = onnx.load(str(raw))
    print(f"  ops: {audit(graph)}")

    replaced = decompose_prelu(graph)

    if not args.no_split_head:
        npz = args.outdir / "prelu_ft_decomp.head.npz"
        split = split_head(graph, npz)
        if split is None:
            print("\n  ! could not identify the detection head - it has NOT been split, and "
                  "quantising it will erase the class scores")
        else:
            print(f"\nsplit off the detection head: {len(split)} raw outputs, decoded in numpy")
            print(f"  head constants -> {npz}")

    onnx.checker.check_model(graph)
    decomposed = args.outdir / "prelu_ft_decomp.onnx"
    onnx.save(graph, str(decomposed))
    print(f"\ndecomposed {replaced} PRelu -> Relu/Mul/Sub")
    print(f"  {decomposed}")

    final = onnx.load(str(decomposed))
    ops = audit(final)
    print(f"  ops: {ops}")

    bad = sorted(set(ops) & KNOWN_UNSUPPORTED)
    silu = find_silu(final)
    if bad:
        print(f"\n  ! unsupported ops remain: {bad}")
    if silu:
        print(f"\n  ! {len(silu)} SiLU patterns remain -- these crash the execution provider")

    print("\nverifying the rewrite is exact")
    worst = verify_equivalent(raw, decomposed)
    print(f"  max abs diff: {worst}")

    # The identity is exact, so anything above float noise means the rewrite is
    # wrong -- most likely a slope that did not broadcast the way PRelu did.
    if worst > 1e-6:
        print("  ! the rewrite changed the model's output", flush=True)
        return 1
    if bad or silu:
        return 1
    print("\nready to quantise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
