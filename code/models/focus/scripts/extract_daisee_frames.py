#!/usr/bin/env python3
import argparse
from pathlib import Path

import cv2


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def parse_args() -> argparse.Namespace:
    root = Path("/home/ryh/thesis")
    parser = argparse.ArgumentParser(description="Extract frames from DAiSEE videos into per-clip folders.")
    parser.add_argument(
        "--videos-root",
        type=Path,
        default=root / "data/raw/DAiSEE/DAiSEE/DataSet",
        help="Root directory containing DAiSEE split subdirectories with video files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data/raw/DAiSEE/frames",
        help="Output root for extracted frames",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val"],
        help="Dataset splits to process",
    )
    parser.add_argument(
        "--sample-every",
        type=int,
        default=10,
        help="Keep one frame every N source frames",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=120,
        help="Maximum number of frames to save per clip",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-extract even if the clip output directory already contains frames",
    )
    return parser.parse_args()


def _iter_videos(split_dir: Path) -> list[Path]:
    return sorted(p for p in split_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


def _canonical_split_name(split: str) -> str:
    mapping = {
        "train": "Train",
        "training": "Train",
        "val": "Validation",
        "valid": "Validation",
        "validation": "Validation",
        "test": "Test",
    }
    return mapping.get(split.lower(), split)


def _output_split_name(split: str) -> str:
    mapping = {
        "Train": "train",
        "Validation": "val",
        "Test": "test",
    }
    return mapping.get(split, split.lower())


def _extract_video(video_path: Path, out_dir: Path, sample_every: int, max_frames: int) -> tuple[int, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    frame_index = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index % sample_every == 0:
            target = out_dir / f"frame_{saved:05d}.jpg"
            cv2.imwrite(str(target), frame)
            saved += 1
            if saved >= max_frames:
                break
        frame_index += 1

    cap.release()
    return frame_index, saved


def main() -> None:
    args = parse_args()
    videos_root = args.videos_root.resolve()
    output_root = args.output.resolve()

    if args.sample_every <= 0:
        raise ValueError("--sample-every must be a positive integer")
    if args.max_frames <= 0:
        raise ValueError("--max-frames must be a positive integer")

    for split in args.splits:
        source_split = _canonical_split_name(split)
        output_split = _output_split_name(source_split)
        split_dir = videos_root / source_split
        if not split_dir.exists():
            print(f"[WARN] split directory not found, skipping: {split_dir}")
            continue

        stats = {
            "videos_found": 0,
            "videos_processed": 0,
            "videos_skipped": 0,
            "frames_saved": 0,
        }

        for video_path in _iter_videos(split_dir):
            stats["videos_found"] += 1
            clip_id = video_path.stem
            clip_out_dir = output_root / output_split / clip_id
            existing_frames = list(clip_out_dir.glob("*.jpg")) if clip_out_dir.exists() else []
            if existing_frames and not args.overwrite:
                stats["videos_skipped"] += 1
                continue

            _, saved = _extract_video(
                video_path=video_path,
                out_dir=clip_out_dir,
                sample_every=args.sample_every,
                max_frames=args.max_frames,
            )
            stats["videos_processed"] += 1
            stats["frames_saved"] += saved

        print(f"[SPLIT] {source_split} -> {output_split}")
        for key, value in stats.items():
            print(f"  - {key}: {value}")

    print(f"[OK] extracted frames are under: {output_root}")


if __name__ == "__main__":
    main()
