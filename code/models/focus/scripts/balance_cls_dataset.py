#!/usr/bin/env python3
import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path("/home/ryh/Thesis")
    parser = argparse.ArgumentParser(
        description="Create a class-balanced copy of an image classification dataset."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "data/processed/daisee_focus_cls_3class",
        help="Input dataset root containing train/ and val/ directories",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data/processed/daisee_focus_cls_3class_balanced",
        help="Output dataset root",
    )
    parser.add_argument(
        "--train-split",
        default="train",
        help="Training split name to balance",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=0,
        help="Target images per class. Defaults to the max class size in train/",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible oversampling",
    )
    parser.add_argument(
        "--link-images",
        action="store_true",
        help="Create symlinks instead of copying files",
    )
    return parser.parse_args()


def _list_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file())


def _place_image(src: Path, dst: Path, link_images: bool) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if link_images:
        dst.symlink_to(src)
    else:
        shutil.copy2(src, dst)


def _copy_split(src_split: Path, dst_split: Path, link_images: bool) -> int:
    written = 0
    for class_dir in sorted(p for p in src_split.iterdir() if p.is_dir()):
        target_dir = dst_split / class_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        for image_path in _list_images(class_dir):
            _place_image(image_path, target_dir / image_path.name, link_images=link_images)
            written += 1
    return written


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    input_root = args.input.resolve()
    output_root = args.output.resolve()
    train_root = input_root / args.train_split
    if not train_root.exists():
        raise FileNotFoundError(f"training split not found: {train_root}")

    class_images = {class_dir.name: _list_images(class_dir) for class_dir in sorted(train_root.iterdir()) if class_dir.is_dir()}
    if not class_images:
        raise ValueError(f"no class directories found under: {train_root}")

    class_counts = {name: len(images) for name, images in class_images.items()}
    if any(count == 0 for count in class_counts.values()):
        empty = [name for name, count in class_counts.items() if count == 0]
        raise ValueError(f"empty class directories found: {empty}")

    target_count = args.target_count or max(class_counts.values())
    print("[INFO] source class counts:")
    for class_name, count in class_counts.items():
        print(f"  - {class_name}: {count}")
    print(f"[INFO] target count per class: {target_count}")

    output_root.mkdir(parents=True, exist_ok=True)

    for split_dir in sorted(p for p in input_root.iterdir() if p.is_dir()):
        dst_split = output_root / split_dir.name
        if split_dir.name != args.train_split:
            written = _copy_split(split_dir, dst_split, link_images=args.link_images)
            print(f"[COPY] split={split_dir.name} images={written}")
            continue

        for class_name, images in class_images.items():
            target_dir = dst_split / class_name
            target_dir.mkdir(parents=True, exist_ok=True)

            for image_path in images:
                _place_image(image_path, target_dir / image_path.name, link_images=args.link_images)

            needed = max(0, target_count - len(images))
            for idx in range(needed):
                src = random.choice(images)
                duplicate_name = f"{src.stem}__dup_{idx:05d}{src.suffix}"
                _place_image(src, target_dir / duplicate_name, link_images=args.link_images)

            print(
                f"[BALANCE] class={class_name} original={len(images)} "
                f"duplicated={needed} total={len(list(target_dir.iterdir()))}"
            )

    print(f"[OK] balanced dataset ready at: {output_root}")


if __name__ == "__main__":
    main()
