# Focus Baseline Weight Documentation

## 1. File Info

- Weight name: `best.pt`
- Absolute path:
  `/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/weights/best.pt`
- Model type: `YOLOv8n-cls`
- Task: focus classification
- Output classes:
  - `high_focus`
  - `low_focus`

## 2. Purpose

This weight is the baseline focus-classification model used in the thesis project.

It is designed to classify a study frame into:
- `high_focus`
- `low_focus`

This model is intended to be integrated with the backend inference pipeline alongside the existing detection model:
- detection model: person / phone / no-person status
- focus model: focus label + confidence score

## 3. Training Source

- Dataset source: `DAiSEE`
- Training data root:
  `/home/ryh/thesis/data/processed/daisee_focus_cls`
- Label mapping:
  - engagement `0-1` -> `low_focus`
  - engagement `2-3` -> `high_focus`

## 4. Training Configuration

Final successful baseline run:

- Run name: `focus_cls_daisee_small_v1_gpu_b8_i192`
- Results directory:
  `/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192`
- Device: `CUDA:0`
- GPU: `NVIDIA GeForce RTX 3060 Laptop GPU`
- Epochs: `5`
- Batch size: `8`
- Image size: `192`
- Workers: `2`

Related files:
- args:
  `/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/args.yaml`
- metrics:
  `/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/results.csv`
- curve:
  `/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/results.png`
- confusion matrix:
  `/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/confusion_matrix.png`

## 5. Validation Result

Baseline validation result from the final successful run:

- top1 accuracy: `0.884`
- top5 accuracy: `1.0`

Note:
Because the dataset is imbalanced, this baseline accuracy should not be interpreted as the final model quality without checking class-wise performance and confusion matrix.

## 6. Backend Integration

The backend loads this weight through environment variable:

- `FOCUS_WEIGHTS=/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/weights/best.pt`

Integrated backend output fields:
- `focus_label`
- `focus_score`
- `focus_enabled`

Relevant backend files:
- `/home/ryh/thesis/code/backend/app/services/inference_service.py`
- `/home/ryh/thesis/code/backend/app/state/runtime.py`
- `/home/ryh/thesis/code/backend/app/main.py`

## 7. Frontend Integration

The frontend inference panel displays:
- detection status
- person count
- phone count
- focus label
- focus score
- classifier enabled state

Relevant frontend files:
- `/home/ryh/thesis/code/frontend/app/src/components/inference/InferencePanel.vue`
- `/home/ryh/thesis/code/frontend/app/src/stores/inference.ts`
- `/home/ryh/thesis/code/frontend/app/src/types/inference.ts`

## 8. Deployment Notes

To deploy this weight on another machine, keep:
- this `best.pt` file
- backend inference code
- frontend integration code if UI display is needed
- Python dependencies:
  - `torch`
  - `ultralytics`
  - `opencv-python`
  - `numpy`
  - `fastapi`
  - `uvicorn`

Recommended environment variables:

```bash
FOCUS_WEIGHTS=/path/to/best.pt
FOCUS_DEVICE=0
```

If GPU is unavailable:

```bash
FOCUS_DEVICE=cpu
```

## 9. Limitations

- This is a baseline, not the final optimized model.
- The dataset is class-imbalanced.
- The model currently performs frame-level classification, not temporal sequence modeling.
- The current label mapping is simplified from DAiSEE engagement levels to binary focus levels.

## 10. Suggested Next Steps

- improve label mapping strategy
- rebalance training data
- evaluate on held-out test data
- add temporal modeling for more robust focus estimation
- replace the baseline weight later without changing backend response format
