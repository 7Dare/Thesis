# Focus Modeling

This module contains scripts for training focus/engagement models for the thesis.

Recommended new direction:

- Dataset: DAiSEE
- Task: focus classification instead of object detection
- Baseline labels:
  - `low_focus`: engagement levels 0-1
  - `high_focus`: engagement levels 2-3

Expected workflow:

1. Download DAiSEE and extract videos or frames under `data/raw/DAiSEE/`.
2. If you only have videos, extract frames with
   `code/models/focus/scripts/extract_daisee_frames.py`.
3. Build a frame-level classification dataset with
   `code/models/focus/scripts/prepare_daisee_focus_cls.py`.
4. Train a classification baseline with
   `code/models/focus/scripts/train_focus_cls.py`.

Suggested local layout:

- `data/raw/DAiSEE/`
- `data/raw/DAiSEE/videos/<split>/<clip_id>.mp4`
- `data/raw/DAiSEE/frames/<split>/<clip_id>/...jpg`
- `data/raw/DAiSEE/labels/<split>.csv`
- `data/processed/daisee_focus_cls/`

Example commands:

```bash
/home/ryh/miniconda3/envs/yolov8/bin/python /home/ryh/thesis/code/models/focus/scripts/extract_daisee_frames.py
/home/ryh/miniconda3/envs/yolov8/bin/python /home/ryh/thesis/code/models/focus/scripts/prepare_daisee_focus_cls.py --link-images
/home/ryh/miniconda3/envs/yolov8/bin/python /home/ryh/thesis/code/models/focus/scripts/train_focus_cls.py --device cpu
```
