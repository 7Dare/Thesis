# Code Workspace

This folder is organized for multi-model research plus backend/frontend development.

## Structure

- `models/`: model training and inference code
- `models/yolo/scripts/`: YOLO train/eval scripts
- `models/yolo/weights/`: local pretrained or exported weights
- `models/yolo/experiments/`: YOLO run artifacts moved from `code/runs`
- `backend/`: server-side code (APIs, services, schedulers)
- `frontend/`: web/app UI code
- `shared/`: shared utilities, schemas, constants
- `tools/`: one-off scripts for dataset checks, conversion, automation

## Conventions

- Keep each model in its own subfolder under `models/`.
- Keep scripts small and task-specific (`train_*.py`, `eval_*.py`, `infer_*.py`).
- Store experiment outputs in `thesis/results/` for thesis tracking.
- Do not mix backend/frontend runtime code with training scripts.
