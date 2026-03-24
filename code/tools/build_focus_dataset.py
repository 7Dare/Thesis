#!/usr/bin/env python3
import argparse
from pathlib import Path

import yaml


CLASS_MAP = {
    1: 0,  # 阅读 -> focused
    2: 0,  # 写字 -> focused
    3: 1,  # 看手机 -> unfocused
    4: 1,  # 分神 -> unfocused
    5: 1,  # 睡觉 -> unfocused
}

CLASS_NAMES = ["focused", "unfocused"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a binary focus YOLO dataset from the existing behavior dataset."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            "/home/ryh/thesis/data/raw/0.355k_university_yolo_Dataset/0.355k_university_yolo_Dataset"
        ),
        help="Source YOLO dataset root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/home/ryh/thesis/data/processed/focus_binary"),
        help="Output YOLO dataset root",
    )
    parser.add_argument(
        "--link-images",
        action="store_true",
        help="Create symlinks for images instead of copying them",
    )
    return parser.parse_args()


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _convert_label_file(src: Path, dst: Path, stats: dict[str, int]) -> None:
    converted: list[str] = []
    for raw_line in _read_lines(src):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            stats["bad_lines"] += 1
            continue
        try:
            cls_id = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:])
        except ValueError:
            stats["bad_lines"] += 1
            continue
        if cls_id not in CLASS_MAP:
            stats["skipped_labels"] += 1
            continue
        if not all(0.0 <= value <= 1.0 for value in (x, y, w, h)):
            stats["invalid_boxes"] += 1
            continue
        converted.append(f"{CLASS_MAP[cls_id]} {x} {y} {w} {h}")
        stats["kept_labels"] += 1

    dst.write_text("\n".join(converted) + ("\n" if converted else ""), encoding="utf-8")


def _prepare_image(src: Path, dst: Path, link_images: bool) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if link_images:
        dst.symlink_to(src)
    else:
        dst.write_bytes(src.read_bytes())


def _process_split(source_root: Path, output_root: Path, split: str, link_images: bool) -> dict[str, int]:
    src_img_dir = source_root / "images" / split
    src_lbl_dir = source_root / "labels" / split
    out_img_dir = output_root / "images" / split
    out_lbl_dir = output_root / "labels" / split
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "images": 0,
        "label_files": 0,
        "kept_labels": 0,
        "skipped_labels": 0,
        "bad_lines": 0,
        "invalid_boxes": 0,
        "missing_label_files": 0,
    }

    for image_path in sorted(p for p in src_img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS):
        stats["images"] += 1
        target_image = out_img_dir / image_path.name
        _prepare_image(image_path, target_image, link_images=link_images)

        src_label = src_lbl_dir / f"{image_path.stem}.txt"
        dst_label = out_lbl_dir / f"{image_path.stem}.txt"
        if src_label.exists():
            stats["label_files"] += 1
            _convert_label_file(src_label, dst_label, stats)
        else:
            stats["missing_label_files"] += 1
            dst_label.write_text("", encoding="utf-8")
    return stats


def _write_data_yaml(output_root: Path) -> Path:
    data = {
        "path": str(output_root),
        "train": "images/train",
        "val": "images/val",
        "nc": len(CLASS_NAMES),
        "names": CLASS_NAMES,
    }
    data_yaml = output_root / "data.yaml"
    data_yaml.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return data_yaml


def main() -> None:
    args = parse_args()
    source_root = args.source.resolve()
    output_root = args.output.resolve()

    if not source_root.exists():
        raise FileNotFoundError(f"source dataset not found: {source_root}")

    summary: dict[str, dict[str, int]] = {}
    for split in ("train", "val"):
        summary[split] = _process_split(source_root, output_root, split, link_images=args.link_images)

    data_yaml = _write_data_yaml(output_root)

    print(f"[OK] focus dataset created: {output_root}")
    print(f"[OK] data.yaml: {data_yaml}")
    for split, stats in summary.items():
        print(f"[SPLIT] {split}")
        for key, value in stats.items():
            print(f"  - {key}: {value}")


if __name__ == "__main__":
    main()
