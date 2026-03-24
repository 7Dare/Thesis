#!/usr/bin/env python3
import argparse
import csv
import shutil
from collections import Counter
from pathlib import Path


FRAME_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_CLASS_MAP = {
    0: "low_focus",
    1: "low_focus",
    2: "high_focus",
    3: "high_focus",
}


def parse_args() -> argparse.Namespace:
    root = Path("/home/ryh/thesis")
    parser = argparse.ArgumentParser(
        description="Prepare a DAiSEE-based frame classification dataset for focus modeling."
    )
    parser.add_argument(
        "--frames-root",
        type=Path,
        default=root / "data/raw/DAiSEE/frames",
        help="Root directory containing extracted frame folders, usually <frames-root>/<split>/<clip_id>/",
    )
    parser.add_argument(
        "--labels-root",
        type=Path,
        default=root / "data/raw/DAiSEE/DAiSEE/Labels",
        help="Directory containing DAiSEE CSV files such as TrainLabels.csv and ValidationLabels.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data/processed/daisee_focus_cls",
        help="Output classification dataset directory",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val"],
        help="Dataset splits to process",
    )
    parser.add_argument(
        "--frames-per-clip",
        type=int,
        default=12,
        help="Maximum number of sampled frames copied per clip",
    )
    parser.add_argument(
        "--link-images",
        action="store_true",
        help="Create symlinks instead of copying frame files",
    )
    parser.add_argument(
        "--engagement-column",
        default="Engagement",
        help="Column name containing DAiSEE engagement label",
    )
    parser.add_argument(
        "--clip-column",
        default="ClipID",
        help="Column name for clip id. Fallbacks are tried automatically if this is missing.",
    )
    return parser.parse_args()


def _find_csv(labels_root: Path, split: str) -> Path:
    normalized = split.lower()
    candidates = [
        labels_root / f"{split}.csv",
        labels_root / f"{split.upper()}.csv",
        labels_root / f"{split.capitalize()}.csv",
        labels_root / split / "labels.csv",
        labels_root / "TrainLabels.csv" if normalized == "train" else labels_root / "_missing_",
        labels_root / "ValidationLabels.csv" if normalized in {"val", "valid", "validation"} else labels_root / "_missing_",
        labels_root / "TestLabels.csv" if normalized == "test" else labels_root / "_missing_",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not find CSV for split '{split}' under {labels_root}")


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError(f"No rows found in {csv_path}")
    return rows


def _pick_clip_id(row: dict[str, str], preferred: str) -> str:
    candidates = [
        preferred,
        "clip",
        "clip_name",
        "clip_id",
        "video",
        "video_id",
        "filename",
    ]
    for key in candidates:
        value = row.get(key)
        if value:
            return Path(value).stem
    raise KeyError(f"Could not infer clip id from row keys: {list(row.keys())}")


def _frame_split_name(split: str) -> str:
    mapping = {
        "train": "train",
        "training": "train",
        "val": "val",
        "valid": "val",
        "validation": "val",
        "test": "test",
    }
    return mapping.get(split.lower(), split.lower())


def _pick_engagement(row: dict[str, str], engagement_column: str) -> int:
    value = row.get(engagement_column)
    if value is None:
        for fallback in ("engagement", "label", "Engagement", "Engagement Level"):
            value = row.get(fallback)
            if value is not None:
                break
    if value is None:
        raise KeyError(f"Could not find engagement label in row keys: {list(row.keys())}")
    return int(float(value))


def _sample_frames(frame_dir: Path, frames_per_clip: int) -> list[Path]:
    frames = sorted(p for p in frame_dir.iterdir() if p.suffix.lower() in FRAME_EXTS)
    if not frames:
        return []
    if len(frames) <= frames_per_clip:
        return frames
    step = len(frames) / frames_per_clip
    return [frames[int(i * step)] for i in range(frames_per_clip)]


def _place_image(src: Path, dst: Path, link_images: bool) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if link_images:
        dst.symlink_to(src)
    else:
        shutil.copy2(src, dst)


def process_split(
    split: str,
    frames_root: Path,
    labels_root: Path,
    output_root: Path,
    frames_per_clip: int,
    link_images: bool,
    clip_column: str,
    engagement_column: str,
) -> dict[str, int]:
    csv_path = _find_csv(labels_root, split)
    rows = _read_rows(csv_path)
    stats = {
        "clips_total": 0,
        "clips_missing_frames": 0,
        "frames_written": 0,
        "rows_skipped": 0,
    }
    class_counter: Counter[str] = Counter()

    for row in rows:
        stats["clips_total"] += 1
        try:
            clip_id = _pick_clip_id(row, clip_column)
            engagement = _pick_engagement(row, engagement_column)
        except Exception:
            stats["rows_skipped"] += 1
            continue

        label_name = DEFAULT_CLASS_MAP.get(engagement)
        if label_name is None:
            stats["rows_skipped"] += 1
            continue

        clip_dir = frames_root / _frame_split_name(split) / clip_id
        if not clip_dir.exists():
            stats["clips_missing_frames"] += 1
            continue

        sampled_frames = _sample_frames(clip_dir, frames_per_clip)
        if not sampled_frames:
            stats["clips_missing_frames"] += 1
            continue

        target_dir = output_root / split / label_name
        target_dir.mkdir(parents=True, exist_ok=True)
        class_counter[label_name] += 1

        for frame in sampled_frames:
            target_name = f"{clip_id}__{frame.name}"
            _place_image(frame, target_dir / target_name, link_images=link_images)
            stats["frames_written"] += 1

    for class_name, count in sorted(class_counter.items()):
        stats[f"clips_{class_name}"] = count
    return stats


def main() -> None:
    args = parse_args()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    for split in args.splits:
        stats = process_split(
            split=split,
            frames_root=args.frames_root.resolve(),
            labels_root=args.labels_root.resolve(),
            output_root=output_root,
            frames_per_clip=args.frames_per_clip,
            link_images=args.link_images,
            clip_column=args.clip_column,
            engagement_column=args.engagement_column,
        )
        print(f"[SPLIT] {split}")
        for key, value in stats.items():
            print(f"  - {key}: {value}")

    print(f"[OK] classification dataset ready at: {output_root}")
    print("[INFO] expected class folders are under split directories, for example train/low_focus")


if __name__ == "__main__":
    main()
