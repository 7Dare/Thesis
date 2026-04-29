#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from typing import Any

from ultralytics import YOLO


def resolve_root() -> Path:
    env_root = os.getenv("THESIS_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    # .../Thesis/code/models/focus/scripts/train_focus_cls.py -> .../Thesis
    return Path(__file__).resolve().parents[4]


def parse_args() -> argparse.Namespace:
    root = resolve_root()
    parser = argparse.ArgumentParser(description="Train a focus classification baseline with Ultralytics.")
    parser.add_argument(
        "--data",
        type=Path,
        default=root / "data/processed/daisee_focus_cls",
        help="Classification dataset root with train/ and val/ folders",
    )
    parser.add_argument(
        "--weights",
        default="yolov8s-cls.pt",
        help="Checkpoint path or model name (e.g. yolov8s-cls.pt)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume from last.pt checkpoint; overrides --weights when provided",
    )
    parser.add_argument(
        "--preset",
        choices=["baseline", "strong"],
        default="strong",
        help="Training preset for common setups",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Target total epochs")
    parser.add_argument("--imgsz", type=int, default=224, help="Image size")
    parser.add_argument("--batch", type=int, default=32, help="Batch size")
    parser.add_argument("--device", default="0", help='Device id, e.g. "0" or "cpu"')
    parser.add_argument("--workers", type=int, default=4, help="Dataloader workers")
    parser.add_argument("--patience", type=int, default=20, help="Early stop patience")
    parser.add_argument("--dropout", type=float, default=0.1, help="Classification head dropout")
    parser.add_argument("--optimizer", default="AdamW", help='Optimizer, e.g. "SGD" or "AdamW"')
    parser.add_argument("--lr0", type=float, default=8e-4, help="Initial learning rate")
    parser.add_argument("--lrf", type=float, default=1e-2, help="Final LR factor")
    parser.add_argument("--weight-decay", type=float, default=1e-3, help="Weight decay")
    parser.add_argument("--cos-lr", action="store_true", help="Use cosine learning rate schedule")
    parser.add_argument("--erasing", type=float, default=0.4, help="Random erasing strength [0,1]")
    parser.add_argument("--auto-augment", default="randaugment", help="Auto augmentation policy")
    parser.add_argument("--project", type=Path, default=root / "results", help="Output project dir")
    parser.add_argument("--name", default="focus_cls_daisee", help="Run name under project/")
    return parser.parse_args()


def resolve_data_dir(root: Path, data_arg: Path) -> Path:
    return data_arg if data_arg.is_absolute() else root / data_arg


def resolve_ckpt(root: Path, raw: str | Path) -> str:
    raw_str = str(raw)
    candidate = Path(raw_str)
    if candidate.is_absolute():
        return str(candidate)
    local = root / candidate
    if local.exists():
        return str(local)
    # Not a local file: keep as model id such as yolov8s-cls.pt
    return raw_str


def preset_overrides(args: argparse.Namespace) -> dict[str, Any]:
    if args.preset == "baseline":
        return {}
    return {
        "optimizer": args.optimizer,
        "lr0": args.lr0,
        "lrf": args.lrf,
        "weight_decay": args.weight_decay,
        "dropout": args.dropout,
        "cos_lr": args.cos_lr,
        "erasing": args.erasing,
        "auto_augment": args.auto_augment,
        "patience": args.patience,
    }


def main() -> None:
    args = parse_args()
    root = resolve_root()
    data_dir = resolve_data_dir(root, args.data)
    project = args.project if args.project.is_absolute() else root / args.project

    if not data_dir.exists():
        raise FileNotFoundError(f"classification dataset not found: {data_dir}")
    if not (data_dir / "train").exists():
        raise FileNotFoundError(f"missing train directory under: {data_dir}")
    if not (data_dir / "val").exists():
        raise FileNotFoundError(f"missing val directory under: {data_dir}")
    resume_ckpt = None
    if args.resume is not None:
        resume_ckpt = resolve_ckpt(root, args.resume)
        if not Path(resume_ckpt).exists():
            raise FileNotFoundError(f"resume checkpoint not found: {resume_ckpt}")
        model_init = resume_ckpt
    else:
        model_init = resolve_ckpt(root, args.weights)

    model = YOLO(model_init)
    train_kwargs = dict(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(project),
        name=args.name,
    )
    train_kwargs.update(preset_overrides(args))
    if resume_ckpt is not None:
        train_kwargs["resume"] = True

    model.train(**train_kwargs)


if __name__ == "__main__":
    main()
