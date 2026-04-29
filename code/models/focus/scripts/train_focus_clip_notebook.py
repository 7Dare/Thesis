#!/usr/bin/env python3
"""
Clip-level DAiSEE focus classification baseline for Kaggle Notebook.

Why this script:
- DAiSEE labels are clip-level, not frame-level.
- This script groups frames by clip, samples K frames per clip, then predicts one clip label.

Run in Kaggle:
  !python /kaggle/working/Thesis/code/models/focus/scripts/train_focus_clip_notebook.py
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms
from torchvision.models import ResNet18_Weights
from PIL import Image


# =========================
# CONFIG (edit these only)
# =========================
DATA_ROOT = Path(
    "/kaggle/input/datasets/renyh7zzzz/daisee-focus-3class-semibalanced/daisee_focus_cls_3class_semibalanced"
)
OUT_DIR = Path("/kaggle/working/Thesis/results/focus_clip_daisee_3class_resnet18_k8")

EPOCHS = 15
BATCH_SIZE = 32
NUM_WORKERS = 2
LR = 3e-4
WEIGHT_DECAY = 1e-4
PATIENCE = 4
SEED = 42

K_FRAMES = 8
IMAGE_SIZE = 224
USE_WEIGHTED_SAMPLER = True
USE_CLASS_WEIGHT_LOSS = True
DROP_DUP_SUFFIX = True  # skip files like "__dup_00001.jpg"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def clip_id_from_filename(name: str) -> str:
    # Expected pattern from your data builder: <clip_id>__<frame_name>.jpg
    # Fallback: stem before first "__"
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
            if DROP_DUP_SUFFIX and "__dup_" in p.name:
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
        train_mode: bool,
    ) -> None:
        self.items = items
        self.k_frames = k_frames
        self.transform = transform
        self.train_mode = train_mode

    def __len__(self) -> int:
        return len(self.items)

    def _sample_indices(self, n: int) -> list[int]:
        if n <= self.k_frames:
            return [i % n for i in range(self.k_frames)]
        if self.train_mode:
            return sorted(random.sample(range(n), self.k_frames))
        step = (n - 1) / (self.k_frames - 1)
        return [int(round(i * step)) for i in range(self.k_frames)]

    def __getitem__(self, idx: int):
        item = self.items[idx]
        frame_paths = item.frame_paths
        inds = self._sample_indices(len(frame_paths))
        images = []
        for i in inds:
            img = Image.open(frame_paths[i]).convert("RGB")
            images.append(self.transform(img))
        # [K, C, H, W], label
        return torch.stack(images, dim=0), item.label


class ClipResNet18(nn.Module):
    def __init__(self, num_classes: int, dropout: float = 0.2):
        super().__init__()
        backbone = models.resnet18(weights=ResNet18_Weights.DEFAULT)
        in_feats = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(in_feats, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, K, C, H, W]
        b, k, c, h, w = x.shape
        x = x.view(b * k, c, h, w)
        feats = self.backbone(x)  # [B*K, D]
        d = feats.shape[-1]
        feats = feats.view(b, k, d).mean(dim=1)  # mean-pool over K frames
        return self.head(feats)


def make_transforms(image_size: int):
    train_tf = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    val_tf = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    return train_tf, val_tf


def accuracy(logits: torch.Tensor, targets: torch.Tensor) -> float:
    preds = logits.argmax(dim=1)
    return (preds == targets).float().mean().item()


def macro_f1_from_confmat(conf: torch.Tensor) -> float:
    # conf[i, j] = count of true i predicted j
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


def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module, num_classes: int):
    model.eval()
    total_loss = 0.0
    total = 0
    total_acc = 0.0
    conf = torch.zeros((num_classes, num_classes), dtype=torch.int64)
    with torch.no_grad():
        for x, y in loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            logits = model(x)
            loss = criterion(logits, y)
            bs = y.size(0)
            total_loss += loss.item() * bs
            total_acc += accuracy(logits, y) * bs
            total += bs
            preds = logits.argmax(dim=1).cpu()
            ys = y.cpu()
            for t, p in zip(ys, preds):
                conf[int(t), int(p)] += 1
    return {
        "loss": total_loss / max(total, 1),
        "acc": total_acc / max(total, 1),
        "macro_f1": macro_f1_from_confmat(conf),
        "confusion_matrix": conf.tolist(),
    }


def main() -> None:
    seed_everything(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    train_root = DATA_ROOT / "train"
    val_root = DATA_ROOT / "val"
    if not train_root.exists() or not val_root.exists():
        raise FileNotFoundError(f"Expected train/ and val/ under {DATA_ROOT}")

    class_names = sorted([d.name for d in train_root.iterdir() if d.is_dir()])
    if not class_names:
        raise ValueError(f"No class directories found under {train_root}")
    class_to_idx = {c: i for i, c in enumerate(class_names)}
    num_classes = len(class_names)

    train_items = build_clip_items(train_root, class_to_idx)
    val_items = build_clip_items(val_root, class_to_idx)
    if not train_items or not val_items:
        raise ValueError("No clip items built. Check filename pattern and dataset path.")

    train_labels = [it.label for it in train_items]
    val_labels = [it.label for it in val_items]
    train_counts = Counter(train_labels)
    val_counts = Counter(val_labels)

    print("Classes:", class_to_idx)
    print("Train clips per class:", {class_names[k]: v for k, v in sorted(train_counts.items())})
    print("Val clips per class  :", {class_names[k]: v for k, v in sorted(val_counts.items())})
    print(f"Train clips: {len(train_items)}, Val clips: {len(val_items)}")

    train_tf, val_tf = make_transforms(IMAGE_SIZE)
    train_ds = ClipDataset(train_items, k_frames=K_FRAMES, transform=train_tf, train_mode=True)
    val_ds = ClipDataset(val_items, k_frames=K_FRAMES, transform=val_tf, train_mode=False)

    sampler = None
    shuffle = True
    if USE_WEIGHTED_SAMPLER:
        # Weight each clip by inverse class frequency
        class_w = {k: 1.0 / v for k, v in train_counts.items()}
        sample_w = [class_w[it.label] for it in train_items]
        sampler = WeightedRandomSampler(sample_w, num_samples=len(sample_w), replacement=True)
        shuffle = False

    train_loader = DataLoader(
        train_ds,
        batch_size=BATCH_SIZE,
        shuffle=shuffle,
        sampler=sampler,
        num_workers=NUM_WORKERS,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=True,
    )

    model = ClipResNet18(num_classes=num_classes).to(DEVICE)

    if USE_CLASS_WEIGHT_LOSS:
        # Lower count -> higher weight
        counts = torch.tensor([train_counts.get(i, 1) for i in range(num_classes)], dtype=torch.float32)
        w = counts.sum() / (counts * len(counts))
        criterion = nn.CrossEntropyLoss(weight=w.to(DEVICE))
    else:
        criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(EPOCHS, 1))
    use_amp = torch.cuda.is_available()
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_f1 = -math.inf
    bad_epochs = 0
    history = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        train_acc = 0.0
        total = 0

        for x, y in train_loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=use_amp):
                logits = model(x)
                loss = criterion(logits, y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            bs = y.size(0)
            train_loss += loss.item() * bs
            train_acc += accuracy(logits, y) * bs
            total += bs

        scheduler.step()

        train_loss /= max(total, 1)
        train_acc /= max(total, 1)
        val_stats = evaluate(model, val_loader, criterion, num_classes)

        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_acc": train_acc,
            "val_loss": val_stats["loss"],
            "val_acc": val_stats["acc"],
            "val_macro_f1": val_stats["macro_f1"],
            "lr": optimizer.param_groups[0]["lr"],
        }
        history.append(row)
        print(
            f"[{epoch:02d}/{EPOCHS}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={row['val_loss']:.4f} val_acc={row['val_acc']:.4f} "
            f"val_macro_f1={row['val_macro_f1']:.4f}"
        )

        ckpt_last = {
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "class_to_idx": class_to_idx,
            "config": {
                "k_frames": K_FRAMES,
                "image_size": IMAGE_SIZE,
            },
            "val_confusion_matrix": val_stats["confusion_matrix"],
        }
        torch.save(ckpt_last, OUT_DIR / "last.pt")

        if row["val_macro_f1"] > best_f1:
            best_f1 = row["val_macro_f1"]
            bad_epochs = 0
            torch.save(ckpt_last, OUT_DIR / "best.pt")
        else:
            bad_epochs += 1
            if bad_epochs >= PATIENCE:
                print(f"Early stop at epoch {epoch}, best val_macro_f1={best_f1:.4f}")
                break

    (OUT_DIR / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"[OK] saved: {OUT_DIR / 'best.pt'}")
    print(f"[OK] saved: {OUT_DIR / 'last.pt'}")
    print(f"[OK] saved: {OUT_DIR / 'history.json'}")


if __name__ == "__main__":
    main()
