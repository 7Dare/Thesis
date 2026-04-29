#!/usr/bin/env python3
"""
Evaluate clip-level focus classifier checkpoint on DAiSEE-style clip dataset.

Run in Kaggle:
  !python /kaggle/working/Thesis/code/models/focus/scripts/eval_focus_clip_notebook.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms
from torchvision.models import ResNet18_Weights


# =========================
# CONFIG (edit these only)
# =========================
DATA_ROOT = Path(
    "/kaggle/input/datasets/renyh7zzzz/daisee-focus-3class-semibalanced/daisee_focus_cls_3class_semibalanced"
)
RUN_DIR = Path("/kaggle/working/Thesis/results/focus_clip_daisee_3class_resnet18_k8")
CKPT = RUN_DIR / "best.pt"

BATCH_SIZE = 16
NUM_WORKERS = 2
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def clip_id_from_filename(name: str) -> str:
    return Path(name).stem.split("__")[0]


@dataclass
class ClipItem:
    clip_id: str
    label: int
    frame_paths: list[Path]


def build_clip_items(split_root: Path, class_to_idx: dict[str, int]) -> list[ClipItem]:
    clip_frames: dict[tuple[str, int], list[Path]] = defaultdict(list)
    for class_name, class_idx in class_to_idx.items():
        class_dir = split_root / class_name
        if not class_dir.exists():
            continue
        for p in class_dir.iterdir():
            if not p.is_file() or not is_image(p):
                continue
            if "__dup_" in p.name:
                continue
            cid = clip_id_from_filename(p.name)
            clip_frames[(cid, class_idx)].append(p)

    items: list[ClipItem] = []
    for (cid, label), paths in clip_frames.items():
        paths = sorted(paths)
        if paths:
            items.append(ClipItem(clip_id=cid, label=label, frame_paths=paths))
    return items


class ClipDataset(Dataset):
    def __init__(
        self,
        items: list[ClipItem],
        k_frames: int,
        transform: transforms.Compose,
    ) -> None:
        self.items = items
        self.k_frames = k_frames
        self.transform = transform

    def __len__(self) -> int:
        return len(self.items)

    def _sample_indices(self, n: int) -> list[int]:
        if n <= self.k_frames:
            return [i % n for i in range(self.k_frames)]
        step = (n - 1) / (self.k_frames - 1)
        return [int(round(i * step)) for i in range(self.k_frames)]

    def __getitem__(self, idx: int):
        item = self.items[idx]
        inds = self._sample_indices(len(item.frame_paths))
        images = []
        for i in inds:
            img = Image.open(item.frame_paths[i]).convert("RGB")
            images.append(self.transform(img))
        return torch.stack(images, dim=0), item.label


class ClipResNet18(nn.Module):
    def __init__(self, num_classes: int, dropout: float = 0.2):
        super().__init__()
        backbone = models.resnet18(weights=ResNet18_Weights.DEFAULT)
        in_feats = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_feats, num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, k, c, h, w = x.shape
        x = x.view(b * k, c, h, w)
        feats = self.backbone(x)
        d = feats.shape[-1]
        feats = feats.view(b, k, d).mean(dim=1)
        return self.head(feats)


def macro_f1_from_confmat(conf: torch.Tensor) -> float:
    num_classes = conf.shape[0]
    f1s = []
    for i in range(num_classes):
        tp = conf[i, i].item()
        fp = conf[:, i].sum().item() - tp
        fn = conf[i, :].sum().item() - tp
        denom = (2 * tp + fp + fn)
        f1 = 0.0 if denom == 0 else (2 * tp / denom)
        f1s.append(f1)
    return float(sum(f1s) / num_classes)


def main() -> None:
    if not CKPT.exists():
        raise FileNotFoundError(f"Checkpoint not found: {CKPT}")
    if not (DATA_ROOT / "val").exists():
        raise FileNotFoundError(f"Validation split not found: {DATA_ROOT / 'val'}")

    state = torch.load(CKPT, map_location="cpu")
    class_to_idx = state["class_to_idx"]
    idx_to_class = {v: k for k, v in class_to_idx.items()}
    num_classes = len(class_to_idx)
    k_frames = int(state.get("config", {}).get("k_frames", 8))
    image_size = int(state.get("config", {}).get("image_size", 224))

    val_items = build_clip_items(DATA_ROOT / "val", class_to_idx)
    if not val_items:
        raise ValueError("No val clip items found.")

    tf = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    val_ds = ClipDataset(val_items, k_frames=k_frames, transform=tf)
    val_loader = DataLoader(
        val_ds,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=True,
    )

    model = ClipResNet18(num_classes=num_classes).to(DEVICE)
    model.load_state_dict(state["model_state"])
    model.eval()

    conf = torch.zeros((num_classes, num_classes), dtype=torch.int64)
    total = 0
    correct = 0
    with torch.no_grad():
        for x, y in val_loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            logits = model(x)
            pred = logits.argmax(dim=1)
            correct += (pred == y).sum().item()
            total += y.size(0)
            for t, p in zip(y.cpu(), pred.cpu()):
                conf[int(t), int(p)] += 1

    top1 = correct / max(total, 1)
    macro_f1 = macro_f1_from_confmat(conf)

    print("===== Clip-level Evaluation =====")
    print(f"Run dir  : {RUN_DIR}")
    print(f"CKPT     : {CKPT}")
    print(f"Val clips: {total}")
    print(f"Top1 Acc : {top1:.4f}")
    print(f"Macro F1 : {macro_f1:.4f}")
    print("Confusion Matrix (rows=true, cols=pred):")
    print(conf.tolist())
    print("Class order:", [idx_to_class[i] for i in range(num_classes)])

    metrics = {
        "top1_acc": top1,
        "macro_f1": macro_f1,
        "confusion_matrix": conf.tolist(),
        "class_order": [idx_to_class[i] for i in range(num_classes)],
        "val_clips": total,
    }
    out_path = RUN_DIR / "eval_metrics.json"
    out_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Saved metrics to: {out_path}")


if __name__ == "__main__":
    main()
