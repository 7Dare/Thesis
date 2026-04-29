#!/usr/bin/env python3
"""
Local entrypoint for DAiSEE multi-task training.

Usage:
  /home/ryh/miniconda3/envs/yolov8/bin/python /home/ryh/Thesis/code/models/focus/scripts/train_focus_multitask_local.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _resolve_base_script() -> Path:
    candidates: list[Path] = []
    if "__file__" in globals():
        candidates.append(Path(__file__).resolve().with_name("train_focus_multitask_notebook.py"))
    candidates.extend(
        [
            Path("/home/ryh/Thesis/code/models/focus/scripts/train_focus_multitask_notebook.py"),
            Path("/kaggle/working/Thesis/code/models/focus/scripts/train_focus_multitask_notebook.py"),
            Path.cwd() / "train_focus_multitask_notebook.py",
        ]
    )
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "Could not locate train_focus_multitask_notebook.py in known locations."
    )


def main() -> None:
    base = _resolve_base_script()
    spec = importlib.util.spec_from_file_location("mt", base)
    mt = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mt
    spec.loader.exec_module(mt)

    # Local-specific config
    mt.RUN_ENV = "local"
    mt.DATASET_ROOT = Path("/home/ryh/Thesis/data/raw/DAiSEE")
    mt.LOCAL_OUT_DIR = Path("/home/ryh/Thesis/results/focus_multitask_gpu_e30_local")
    mt.EPOCHS = 30
    mt.BATCH_SIZE = 64
    mt.IMAGE_SIZE = 224
    mt.MAX_FRAMES_PER_CLIP = 12
    mt.NUM_WORKERS = 4

    mt.main()


if __name__ == "__main__":
    main()
