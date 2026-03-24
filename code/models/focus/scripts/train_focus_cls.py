#!/usr/bin/env python3
import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    root = Path("/home/ryh/thesis")
    parser = argparse.ArgumentParser(description="Train a focus classification baseline with Ultralytics.")
    parser.add_argument(
        "--data",
        type=Path,
        default=root / "data/processed/daisee_focus_cls",
        help="Classification dataset root with train/ and val/ folders",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=root / "code/models/focus/weights/yolov8n-cls.pt",
        help="Local classification checkpoint path",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=192, help="Image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--device", default="0", help='Device id, e.g. "0" or "cpu"')
    parser.add_argument("--workers", type=int, default=2, help="Dataloader workers")
    parser.add_argument("--project", type=Path, default=root / "results", help="Output project dir")
    parser.add_argument("--name", default="focus_cls_daisee", help="Run name under project/")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path("/home/ryh/thesis")
    data_dir = args.data if args.data.is_absolute() else root / args.data
    weights = args.weights if args.weights.is_absolute() else root / args.weights
    project = args.project if args.project.is_absolute() else root / args.project

    if not data_dir.exists():
        raise FileNotFoundError(f"classification dataset not found: {data_dir}")
    if not (data_dir / "train").exists():
        raise FileNotFoundError(f"missing train directory under: {data_dir}")
    if not (data_dir / "val").exists():
        raise FileNotFoundError(f"missing val directory under: {data_dir}")
    if not weights.exists():
        raise FileNotFoundError(
            f"classification weights not found: {weights}. "
            "Place yolov8n-cls.pt in /home/ryh/thesis/code/models/focus/weights/"
        )

    model = YOLO(str(weights))
    model.train(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(project),
        name=args.name,
    )


if __name__ == "__main__":
    main()
