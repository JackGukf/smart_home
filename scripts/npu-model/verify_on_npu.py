#!/usr/bin/env python3
"""Prove a model actually runs on the Zhouyi NPU, and measure how fast.

Run it ON the board, from the detector's Python 3.11 environment:

    cd ~/smart_home_AI/deploy/npu
    PYTHONPATH=~/smart_home_AI ~/npu-venv/bin/python \\
        ~/smart_home_AI/scripts/npu-model/verify_on_npu.py --model <path>

Why a separate script rather than just starting the service: on this device a
model that runs is not proof it ran on the NPU.  Unsupported nodes fall back to
the CPU **silently**, so a benchmark can report a perfectly good number that
describes the CPU.  Setting ``session.disable_cpu_ep_fallback`` turns that
fallback into a hard error, which makes successful session creation the actual
proof -- and it is the reason an earlier conclusion about this device was wrong.

The other trap is the layer library.  The Compass runtime resolves it from
``./operator`` relative to the *working directory*; without it you get
``[ERROR][init:145]Cannot find layerlib`` followed by heap corruption rather
than a clean failure.  This script checks for it before touching the runtime.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path


def _decoder(model_path: "Path", session) -> "object | None":
    """The numpy head this model needs, if it was exported with its head split off."""
    sys.path.insert(0, str(Path.home() / "smart_home_AI"))
    from src.python.npu_detector import HeadDecoder, head_meta_for

    if len(session.get_outputs()) <= 2:
        return None
    meta = head_meta_for(model_path)
    if meta is None:
        raise SystemExit(f"{model_path.name} has its head split off but "
                         f"prelu_ft_decomp.head.npz is not beside it")
    return HeadDecoder(meta)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, default=Path.home() / "smart_home_AI" / "deploy" / "npu",
                    help="directory holding the ./operator symlink")
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--allow-cpu-fallback", action="store_true",
                    help="diagnostic only: shows WHERE it falls back instead of failing")
    ap.add_argument("--frame-from", default="", help="go2rtc stream name, to run one real frame")
    ap.add_argument("--go2rtc", default="http://127.0.0.1:1984")
    ap.add_argument("--compare-cpu", action="store_true",
                    help="run the same input through the CPU provider and diff the outputs")
    args = ap.parse_args()

    if not args.model.is_file():
        print(f"no model at {args.model}", file=sys.stderr)
        return 1

    operator = args.workdir / "operator"
    if not operator.exists():
        print(f"no layer library at {operator} -- the runtime would corrupt the heap "
              f"rather than fail cleanly.\nCreate it: ln -sfn "
              f"/usr/share/cix/lib/onnxruntime/operator {operator}", file=sys.stderr)
        return 1
    os.chdir(args.workdir)
    print(f"working directory: {args.workdir}  (layerlib -> {operator.resolve()})")

    import numpy as np
    import onnxruntime as ort

    providers = ort.get_available_providers()
    print(f"available providers: {providers}")
    if "ZhouyiExecutionProvider" not in providers:
        print("ZhouyiExecutionProvider is not available -- wrong interpreter or the "
              "onnxruntime-zhouyi wheel is not installed", file=sys.stderr)
        return 1

    options = ort.SessionOptions()
    if not args.allow_cpu_fallback:
        # The whole point. Without this a partially-unsupported graph runs
        # happily, half on the CPU, and reports a number that means nothing.
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

    print(f"\ncreating session (cpu fallback "
          f"{'ALLOWED - diagnostic' if args.allow_cpu_fallback else 'DISABLED - a fallback is now a hard error'})")
    started = time.time()
    try:
        session = ort.InferenceSession(str(args.model), options, providers=["ZhouyiExecutionProvider"])
    except Exception as exc:  # the failure text is the diagnosis, so print it whole
        print(f"\nFAILED to place the graph on the NPU after {time.time() - started:.1f}s:\n  {exc}",
              file=sys.stderr)
        print("\n  'Connected graph is required!' means the partition fragmented -- too many\n"
              "  unsupported nodes. Re-run with --allow-cpu-fallback to see where.", file=sys.stderr)
        return 1
    compile_s = time.time() - started

    name = session.get_inputs()[0].name
    shape = [d if isinstance(d, int) else 1 for d in session.get_inputs()[0].shape]
    print(f"  session ready in {compile_s:.1f}s")
    print(f"  input {name} {shape} -> output {session.get_outputs()[0].shape}")
    print(f"  providers in use: {session.get_providers()}")

    rng = np.random.default_rng(0)
    blob = rng.uniform(0.0, 1.0, size=shape).astype(np.float32)

    for _ in range(args.warmup):
        session.run(None, {name: blob})

    times = []
    for _ in range(args.runs):
        t0 = time.perf_counter()
        session.run(None, {name: blob})
        times.append(time.perf_counter() - t0)

    mean = statistics.mean(times)
    print(f"\n{args.runs} inferences on the NPU:")
    print(f"  mean   {mean * 1000:7.1f} ms  ->  {1 / mean:5.1f} fps")
    print(f"  median {statistics.median(times) * 1000:7.1f} ms")
    print(f"  min    {min(times) * 1000:7.1f} ms   max {max(times) * 1000:7.1f} ms")

    if args.compare_cpu:
        # Placement is not correctness. The Zhouyi provider implements its own
        # INT8 kernels, so a graph can sit entirely on the NPU and still produce
        # different numbers than the CPU provider the model was scored on.
        print("\ncomparing NPU output against the CPU provider on identical input")
        cpu_opts = ort.SessionOptions()
        cpu_opts.log_severity_level = 3
        cpu = ort.InferenceSession(str(args.model), cpu_opts, providers=["CPUExecutionProvider"])
        cpu_name = cpu.get_inputs()[0].name

        sys.path.insert(0, str(Path.home() / "smart_home_AI"))
        from src.python.npu_detector import merge_outputs as _merge

        head = _decoder(args.model, session)
        worst = 0.0
        for trial in range(3):
            probe = rng.uniform(0.0, 1.0, size=shape).astype(np.float32)
            # Decoded first, so a split-head model is compared as detections
            # rather than as raw tensors - the scores are the half quantisation
            # kills, and they only exist after the head has run.
            on_npu = _merge(session.run(None, {name: probe}), head).astype(np.float64)
            on_cpu = _merge(cpu.run(None, {cpu_name: probe}), head).astype(np.float64)
            diff = float(np.max(np.abs(on_npu - on_cpu)))
            worst = max(worst, diff)
            if trial == 0:
                # Class scores are the last 80 rows and are already sigmoid'd in
                # the head, so they must lie in [0,1]; saturation at exactly 1.0
                # is the signature of a broken output scale.
                npu_scores, cpu_scores = on_npu[0, 4:, :], on_cpu[0, 4:, :]
                print(f"  class scores  NPU max {npu_scores.max():.4f} mean {npu_scores.mean():.4f} "
                      f"| at 1.0: {int((npu_scores >= 0.999).sum())}")
                print(f"  class scores  CPU max {cpu_scores.max():.4f} mean {cpu_scores.mean():.4f} "
                      f"| at 1.0: {int((cpu_scores >= 0.999).sum())}")
                print(f"  box coords    NPU max {on_npu[0, :4, :].max():.1f} "
                      f"| CPU max {on_cpu[0, :4, :].max():.1f}")
        print(f"  worst abs diff over 3 inputs: {worst:.4f}")
        if worst > 0.05:
            print("  ! the NPU and CPU disagree materially -- the accuracy measured on the\n"
                  "    workstation does NOT describe what this device produces")

    if args.frame_from:
        print(f"\nrunning one real frame from {args.frame_from}")
        sys.path.insert(0, str(Path.home() / "smart_home_AI"))
        from src.python.npu_detector import (decode, grab_frame, head_meta_for,
                                             merge_outputs, to_input, HeadDecoder)

        frame = grab_frame(args.go2rtc, args.frame_from)
        if frame is None:
            print(f"  could not fetch a frame from {args.frame_from}")
        else:
            inp, scale, pad_x, pad_y = to_input(frame, args.imgsz)
            output = merge_outputs(session.run(None, {name: inp}), _decoder(args.model, session))
            found = decode(output, scale, pad_x, pad_y, frame.shape[:2], 0.25, 0.45, None)
            print(f"  frame {frame.shape} -> {len(found)} detections")
            for det in found[:8]:
                print(f"    {det.label:<14} {det.confidence:.2f} {det.box}")

    print("\nverified: the graph is on the NPU, with CPU fallback disabled"
          if not args.allow_cpu_fallback else "\ndiagnostic run - fallback was allowed, this proves nothing about placement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
