#!/usr/bin/env python3
"""
Notebook-friendly training script for focus classification (Ultralytics YOLO-CLS).

Usage in Kaggle Notebook:
1) Put this file under /kaggle/working/Thesis/code/models/focus/scripts/
2) Edit the CONFIG section below if needed
3) Run:
   !python /kaggle/working/Thesis/code/models/focus/scripts/train_focus_cls_notebook.py
"""

from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO


# =========================
# CONFIG (edit these only)
# =========================
DATA_DIR = Path(
    "/kaggle/input/datasets/renyh7zzzz/daisee-focus-3class-semibalanced/"
    "data/processed/daisee_focus_cls_3class_semibalanced"
)

# Option A: start from model name
WEIGHTS = "yolov8m-cls.pt"

# Option B: resume from previous last.pt
RESUME_CKPT = None
# Example:
# RESUME_CKPT = Path(
#     "/kaggle/working/Thesis/results/"
#     "focus_cls_daisee_3class_semibalanced_t4_b512_i256_e10/weights/last.pt"
# )

EPOCHS = 30
IMGSZ = 224
BATCH = 64
DEVICE = 0
WORKERS = 4

# Strong preset (recommended)
OPTIMIZER = "AdamW"
LR0 = 8e-4
LRF = 1e-2
WEIGHT_DECAY = 1e-3
DROPOUT = 0.1
PATIENCE = 20
COS_LR = True
ERASING = 0.4
AUTO_AUGMENT = "randaugment"

PROJECT = Path("/kaggle/working/Thesis/results")
NAME = "focus_cls_daisee_3class_semibalanced_t4_b64_i224_e30_mcls"


def check_inputs() -> None:
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_DIR}")
    if not (DATA_DIR / "train").exists():
        raise FileNotFoundError(f"Missing train directory: {DATA_DIR / 'train'}")
    if not (DATA_DIR / "val").exists():
        raise FileNotFoundError(f"Missing val directory: {DATA_DIR / 'val'}")

    if RESUME_CKPT is not None and not Path(RESUME_CKPT).exists():
        raise FileNotFoundError(f"Resume checkpoint not found: {RESUME_CKPT}")


def main() -> None:
    check_inputs()
    PROJECT.mkdir(parents=True, exist_ok=True)

    if RESUME_CKPT is not None:
        model = YOLO(str(RESUME_CKPT))
        train_kwargs = dict(resume=True)
    else:
        model = YOLO(str(WEIGHTS))
        train_kwargs = {}

    train_kwargs.update(
        dict(
            data=str(DATA_DIR),
            epochs=EPOCHS,
            imgsz=IMGSZ,
            batch=BATCH,
            device=DEVICE,
            workers=WORKERS,
            optimizer=OPTIMIZER,
            lr0=LR0,
            lrf=LRF,
            weight_decay=WEIGHT_DECAY,
            dropout=DROPOUT,
            patience=PATIENCE,
            cos_lr=COS_LR,
            erasing=ERASING,
            auto_augment=AUTO_AUGMENT,
            project=str(PROJECT),
            name=NAME,
            exist_ok=True,
        )
    )

    print("========== Training Config ==========")
    print(f"DATA_DIR   : {DATA_DIR}")
    print(f"WEIGHTS    : {WEIGHTS}")
    print(f"RESUME_CKPT: {RESUME_CKPT}")
    print(f"EPOCHS     : {EPOCHS}")
    print(f"IMGSZ/BATCH: {IMGSZ}/{BATCH}")
    print(f"PROJECT    : {PROJECT}")
    print(f"NAME       : {NAME}")
    print("=====================================")

    model.train(**train_kwargs)

    run_dir = PROJECT / NAME
    print("\nTraining complete.")
    print(f"Run dir: {run_dir}")
    print(f"results.csv: {(run_dir / 'results.csv').exists()}")
    print(f"best.pt: {(run_dir / 'weights/best.pt').exists()}")
    print(f"last.pt: {(run_dir / 'weights/last.pt').exists()}")


if __name__ == "__main__":
    main()
