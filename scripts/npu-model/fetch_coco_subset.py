#!/usr/bin/env python3
"""Build a COCO subset for finetuning the NPU detection model.

The board's NPU cannot run stock YOLOv8 (SiLU crashes the execution provider),
so the model in use is a PReLU variant finetuned to recover the accuracy the
activation swap destroys.  That finetune needs images.

Downloads only the images it selects, rather than the 19 GB ``train2017.zip``.
COCO serves images individually, and a 16k subset is ~2.5 GB, so this turns a
100-minute download into a few minutes.  Re-running skips what is already on
disk, so an interrupted fetch resumes.

Everything here is deterministic given ``--seed``.  That matters more than it
looks: the previous model was scored on a held-out split that lived only on the
board and died with it, so its numbers cannot be reproduced or compared against.
A split you can regenerate from a seed is the fix.

    python3 scripts/npu-model/fetch_coco_subset.py --root ~/npu-training/coco
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

IMAGE_URL = "http://images.cocodataset.org/{split}/{file_name}"

# COCO category ids run 1..90 with gaps; YOLO wants a dense 0..79.  Sorting the
# ids gives exactly the ultralytics class order, so a model trained here is
# scored and deployed against the same names.
def dense_class_map(categories: list[dict]) -> dict[int, int]:
    ordered = sorted(c["id"] for c in categories)
    return {cat_id: index for index, cat_id in enumerate(ordered)}


def class_names(categories: list[dict]) -> list[str]:
    by_id = {c["id"]: c["name"] for c in categories}
    return [by_id[cat_id] for cat_id in sorted(by_id)]


def write_yolo_labels(
    images: list[dict],
    anns_by_image: dict[int, list[dict]],
    class_map: dict[int, int],
    label_dir: Path,
) -> int:
    """One .txt per image: ``class cx cy w h``, all normalised to [0, 1]."""
    label_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for image in images:
        width, height = image["width"], image["height"]
        lines = []
        for ann in anns_by_image.get(image["id"], []):
            # iscrowd regions have no usable box for detection training.
            if ann.get("iscrowd"):
                continue
            x, y, w, h = ann["bbox"]
            if w <= 0 or h <= 0:
                continue
            cx, cy = (x + w / 2) / width, (y + h / 2) / height
            nw, nh = w / width, h / height
            # Clip rather than drop: COCO boxes can sit a pixel outside.
            cx, cy = min(max(cx, 0.0), 1.0), min(max(cy, 0.0), 1.0)
            nw, nh = min(nw, 1.0), min(nh, 1.0)
            lines.append(f"{class_map[ann['category_id']]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
        # An image with no annotations is still a valid negative sample, so the
        # file is written empty rather than skipped.
        (label_dir / f"{Path(image['file_name']).stem}.txt").write_text("\n".join(lines))
        written += 1
    return written


def fetch_images(images: list[dict], split: str, dest: Path, workers: int) -> tuple[int, int]:
    dest.mkdir(parents=True, exist_ok=True)
    todo = [im for im in images if not (dest / im["file_name"]).exists()]
    print(f"  {len(images) - len(todo)} already present, fetching {len(todo)}", flush=True)

    def one(image: dict) -> bool:
        url = IMAGE_URL.format(split=split, file_name=image["file_name"])
        target = dest / image["file_name"]
        partial = target.with_suffix(".part")
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                partial.write_bytes(response.read())
            # Rename only once complete, so an interrupted run leaves no
            # truncated JPEG that a later run would happily skip.
            partial.rename(target)
            return True
        except (urllib.error.URLError, OSError, TimeoutError):
            partial.unlink(missing_ok=True)
            return False

    ok = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, im): im for im in todo}
        for done, future in enumerate(as_completed(futures), 1):
            if future.result():
                ok += 1
            else:
                failed += 1
            if done % 500 == 0 or done == len(todo):
                print(f"    {done}/{len(todo)} ({failed} failed)", flush=True)
    return ok, failed


def select(split_json: Path, count: int, seed: int, exclude: set[int] | None = None) -> tuple[list[dict], dict]:
    data = json.loads(split_json.read_text())
    images = sorted(data["images"], key=lambda im: im["id"])
    if exclude:
        images = [im for im in images if im["id"] not in exclude]
    if count and count < len(images):
        images = sorted(random.Random(seed).sample(images, count), key=lambda im: im["id"])
    return images, data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path.home() / "npu-training" / "coco")
    ap.add_argument("--train-images", type=int, default=16000, help="0 for all of train2017")
    ap.add_argument("--val-images", type=int, default=1000, help="held-out eval split from val2017")
    ap.add_argument("--seed", type=int, default=0, help="the split is reproducible from this")
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    ann_dir = args.root / "annotations"
    if not (ann_dir / "instances_val2017.json").exists():
        print(f"missing {ann_dir}/instances_val2017.json - unpack "
              "annotations_trainval2017.zip there first", file=sys.stderr)
        return 1

    manifest: dict[str, object] = {"seed": args.seed}

    for split, count, ann_name in (
        ("val2017", args.val_images, "instances_val2017.json"),
        ("train2017", args.train_images, "instances_train2017.json"),
    ):
        print(f"\n{split}: selecting", flush=True)
        images, data = select(ann_dir / ann_name, count, args.seed)
        print(f"  {len(images)} images", flush=True)

        anns_by_image: dict[int, list[dict]] = {}
        wanted = {im["id"] for im in images}
        for ann in data["annotations"]:
            if ann["image_id"] in wanted:
                anns_by_image.setdefault(ann["image_id"], []).append(ann)

        ok, failed = fetch_images(images, split, args.root / "images" / split, args.workers)
        if failed:
            print(f"  ! {failed} images failed; re-run to retry them", file=sys.stderr)

        # Label only what actually landed, so a partial fetch cannot produce a
        # label file with no image beside it.
        present = [im for im in images if (args.root / "images" / split / im["file_name"]).exists()]
        written = write_yolo_labels(present, anns_by_image, dense_class_map(data["categories"]),
                                    args.root / "labels" / split)
        print(f"  {written} label files", flush=True)
        manifest[split] = {"selected": len(images), "present": len(present), "downloaded": ok}
        names = class_names(data["categories"])

    yaml_path = args.root / "coco-subset.yaml"
    yaml_path.write_text(
        "# Generated by scripts/npu-model/fetch_coco_subset.py -- do not hand-edit.\n"
        f"# Reproduce with --seed {args.seed}.\n"
        f"path: {args.root}\n"
        "train: images/train2017\n"
        "val: images/val2017\n"
        "names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(names))
    )
    (args.root / "subset-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {yaml_path}")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
