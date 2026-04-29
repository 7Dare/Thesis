#!/usr/bin/env python3
"""
Single-frame multi-task DAiSEE training
(Boredom + Engagement + Confusion + Frustration).

Designed for Kaggle Notebook direct run:
  !python /kaggle/working/Thesis/code/models/focus/scripts/train_focus_multitask_notebook.py
"""

from __future__ import annotations

import csv
import json
import random
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms
from torchvision.models import ResNet18_Weights


# =========================
# CONFIG (edit these only)
# =========================
# Raw dataset root (one setting only).
# Supported layouts include:
# - <DATASET_ROOT>/frames + <DATASET_ROOT>/DAiSEE/Labels
# - <DATASET_ROOT>/DAiSEE/frames + <DATASET_ROOT>/DAiSEE/Labels
# - <DATASET_ROOT>/frames + <DATASET_ROOT>/Labels
#
# Local default:
#   /home/ryh/Thesis/data/raw/DAiSEE
#
# Kaggle example:
#   /kaggle/input/<your-daisee-raw-dataset>
DATASET_ROOT = Path("/home/ryh/Thesis/data/raw/DAiSEE")

RUN_ENV = "auto"  # "auto" | "local" | "kaggle"
LOCAL_OUT_DIR = Path("/home/ryh/Thesis/results/focus_multitask_gpu_e30_local")
KAGGLE_OUT_DIR = Path("/kaggle/working/results/focus_multitask_gpu_e30_kaggle")

EPOCHS = 30
BATCH_SIZE = 64
IMAGE_SIZE = 224
MAX_FRAMES_PER_CLIP = 12
NUM_WORKERS = 4
SEED = 42

LR = 3e-4
WEIGHT_DECAY = 1e-4
PATIENCE = 5

USE_WEIGHTED_SAMPLER = True
USE_CLASS_WEIGHT_LOSS = True

# Loss weights for the four tasks
W_BOREDOM = 0.7
W_ENGAGEMENT = 1.0
W_CONFUSION = 0.7
W_FRUSTRATION = 0.7

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class FrameItem:
    path: Path
    boredom: int
    engagement: int
    confusion: int
    frustration: int


def _read_label_csv(path: Path) -> dict[str, tuple[int, int, int, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing label csv: {path}")
    table: dict[str, tuple[int, int, int, int]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clip = Path(row["ClipID"]).stem
            b = int(float(row["Boredom"]))
            e = int(float(row["Engagement"]))
            c = int(float(row["Confusion"]))
            fr = int(float(row.get("Frustration ", row.get("Frustration", 0))))
            table[clip] = (b, e, c, fr)
    return table


def resolve_paths(dataset_root: Path) -> tuple[Path, Path]:
    root = dataset_root.resolve()
    frame_candidates = [
        root / "frames",
        root / "DAiSEE" / "frames",
    ]
    label_candidates = [
        root / "DAiSEE" / "Labels",
        root / "Labels",
    ]

    frames_root = next((p for p in frame_candidates if p.exists()), None)
    labels_root = next((p for p in label_candidates if p.exists()), None)

    if frames_root is None:
        raise FileNotFoundError(
            "Could not find frames directory. Tried:\n"
            + "\n".join(f"  - {p}" for p in frame_candidates)
            + "\nHint: extract raw videos first so you have frames/train and frames/val."
        )
    if labels_root is None:
        raise FileNotFoundError(
            "Could not find Labels directory. Tried:\n" + "\n".join(f"  - {p}" for p in label_candidates)
        )

    return frames_root, labels_root


def resolve_dataset_root(preferred_root: Path, env: str) -> Path:
    # 1) Use preferred root if valid.
    try:
        resolve_paths(preferred_root)
        return preferred_root.resolve()
    except Exception:
        pass

    # 2) Common Kaggle locations.
    candidates: list[Path] = []
    if env == "kaggle":
        candidates.extend(
            [
                Path("/kaggle/working/daisee_raw"),
                Path("/kaggle/working"),
            ]
        )
        input_root = Path("/kaggle/input")
        if input_root.exists():
            # First-level and second-level dirs under /kaggle/input
            for p in sorted(input_root.iterdir()):
                if p.is_dir():
                    candidates.append(p)
                    for q in sorted(p.iterdir()):
                        if q.is_dir():
                            candidates.append(q)

    # 3) Validate candidates.
    for c in candidates:
        try:
            resolve_paths(c)
            return c.resolve()
        except Exception:
            continue

    raise FileNotFoundError(
        f"Could not resolve dataset root from preferred path: {preferred_root}\n"
        "If running on Kaggle, set DATASET_ROOT to your extracted path, e.g.:\n"
        "  /kaggle/working/daisee_raw\n"
        "or a dataset mount under /kaggle/input/<dataset-name>."
    )


def _sample_paths(paths: list[Path], max_frames: int, train: bool) -> list[Path]:
    if not paths:
        return []
    if len(paths) <= max_frames:
        return paths
    if train:
        return sorted(random.sample(paths, max_frames))
    step = len(paths) / max_frames
    return [paths[int(i * step)] for i in range(max_frames)]


def build_items(split: str, frames_root: Path, labels_root: Path) -> list[FrameItem]:
    split_norm = {"train": "train", "val": "val", "validation": "val", "valid": "val"}.get(split.lower(), split.lower())
    csv_name = "TrainLabels.csv" if split_norm == "train" else "ValidationLabels.csv"
    label_map = _read_label_csv(labels_root / csv_name)

    split_dir = frames_root / split_norm
    if not split_dir.exists():
        raise FileNotFoundError(f"Missing frames split dir: {split_dir}")

    items: list[FrameItem] = []
    missing_clip = 0
    for clip_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        clip_id = clip_dir.name
        label = label_map.get(clip_id)
        if label is None:
            missing_clip += 1
            continue
        b, e, c, fr = label
        frame_paths = sorted([p for p in clip_dir.iterdir() if p.is_file() and is_image(p)])
        sampled = _sample_paths(frame_paths, MAX_FRAMES_PER_CLIP, train=(split_norm == "train"))
        for p in sampled:
            items.append(FrameItem(path=p, boredom=b, engagement=e, confusion=c, frustration=fr))

    print(f"[{split_norm}] frame items: {len(items)}, clips without labels: {missing_clip}")
    return items


class DaiseeFrameMultiTaskDataset(Dataset):
    def __init__(self, items: list[FrameItem], tf: transforms.Compose):
        self.items = items
        self.tf = tf

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int):
        item = self.items[idx]
        img = Image.open(item.path).convert("RGB")
        x = self.tf(img)
        y = torch.tensor([item.boredom, item.engagement, item.confusion, item.frustration], dtype=torch.long)
        return x, y


class MultiTaskResNet18(nn.Module):
    def __init__(self, dropout: float = 0.2):
        super().__init__()
        backbone = models.resnet18(weights=ResNet18_Weights.DEFAULT)
        d = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.drop = nn.Dropout(dropout)
        self.head_boredom = nn.Linear(d, 4)
        self.head_engagement = nn.Linear(d, 4)
        self.head_confusion = nn.Linear(d, 4)
        self.head_frustration = nn.Linear(d, 4)

    def forward(self, x: torch.Tensor):
        feat = self.backbone(x)
        feat = self.drop(feat)
        return {
            "boredom": self.head_boredom(feat),
            "engagement": self.head_engagement(feat),
            "confusion": self.head_confusion(feat),
            "frustration": self.head_frustration(feat),
        }


def macro_f1_from_preds(trues: list[int], preds: list[int], num_classes: int = 4) -> float:
    conf = [[0 for _ in range(num_classes)] for _ in range(num_classes)]
    for t, p in zip(trues, preds):
        conf[t][p] += 1
    f1s = []
    for i in range(num_classes):
        tp = conf[i][i]
        fp = sum(conf[r][i] for r in range(num_classes)) - tp
        fn = sum(conf[i][c] for c in range(num_classes)) - tp
        denom = 2 * tp + fp + fn
        f1s.append(0.0 if denom == 0 else (2 * tp / denom))
    return float(sum(f1s) / num_classes)


def inverse_freq_weights(labels: list[int], num_classes: int = 4) -> torch.Tensor:
    c = Counter(labels)
    counts = torch.tensor([max(1, c.get(i, 0)) for i in range(num_classes)], dtype=torch.float32)
    return counts.sum() / (counts * len(counts))


def evaluate(model: nn.Module, loader: DataLoader, crit_b, crit_e, crit_c, crit_f):
    model.eval()
    total = 0
    total_loss = 0.0

    true_b, pred_b = [], []
    true_e, pred_e = [], []
    true_c, pred_c = [], []
    true_f, pred_f = [], []

    with torch.no_grad():
        for x, y in loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)

            out = model(x)
            lb = crit_b(out["boredom"], y[:, 0])
            le = crit_e(out["engagement"], y[:, 1])
            lc = crit_c(out["confusion"], y[:, 2])
            lf = crit_f(out["frustration"], y[:, 3])
            loss = W_BOREDOM * lb + W_ENGAGEMENT * le + W_CONFUSION * lc + W_FRUSTRATION * lf

            bs = y.size(0)
            total += bs
            total_loss += loss.item() * bs

            pb = out["boredom"].argmax(dim=1)
            pe = out["engagement"].argmax(dim=1)
            pc = out["confusion"].argmax(dim=1)
            pf = out["frustration"].argmax(dim=1)

            true_b.extend(y[:, 0].cpu().tolist())
            pred_b.extend(pb.cpu().tolist())
            true_e.extend(y[:, 1].cpu().tolist())
            pred_e.extend(pe.cpu().tolist())
            true_c.extend(y[:, 2].cpu().tolist())
            pred_c.extend(pc.cpu().tolist())
            true_f.extend(y[:, 3].cpu().tolist())
            pred_f.extend(pf.cpu().tolist())

    def acc(t: list[int], p: list[int]) -> float:
        return float(sum(int(a == b) for a, b in zip(t, p)) / max(1, len(t)))

    metrics = {
        "loss": total_loss / max(1, total),
        "boredom_acc": acc(true_b, pred_b),
        "boredom_macro_f1": macro_f1_from_preds(true_b, pred_b),
        "engagement_acc": acc(true_e, pred_e),
        "engagement_macro_f1": macro_f1_from_preds(true_e, pred_e),
        "confusion_acc": acc(true_c, pred_c),
        "confusion_macro_f1": macro_f1_from_preds(true_c, pred_c),
        "frustration_acc": acc(true_f, pred_f),
        "frustration_macro_f1": macro_f1_from_preds(true_f, pred_f),
    }
    metrics["avg_macro_f1"] = (
        metrics["boredom_macro_f1"]
        + metrics["engagement_macro_f1"]
        + metrics["confusion_macro_f1"]
        + metrics["frustration_macro_f1"]
    ) / 4.0
    return metrics


def gpu_runtime_stats() -> dict[str, float | int | str]:
    if not torch.cuda.is_available():
        return {"device": "cpu"}

    used_mb = torch.cuda.memory_allocated() / (1024 * 1024)
    reserved_mb = torch.cuda.memory_reserved() / (1024 * 1024)
    stats: dict[str, float | int | str] = {
        "device": "cuda",
        "gpu_mem_used_mb": round(used_mb, 2),
        "gpu_mem_reserved_mb": round(reserved_mb, 2),
    }

    try:
        result = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
        if result:
            util, mem_used, mem_total, temp = [x.strip() for x in result.splitlines()[0].split(",")]
            stats.update(
                {
                    "gpu_util_pct": int(util),
                    "nvsmi_mem_used_mb": int(mem_used),
                    "nvsmi_mem_total_mb": int(mem_total),
                    "gpu_temp_c": int(temp),
                }
            )
    except Exception:
        # Keep training robust even if nvidia-smi is unavailable.
        pass

    return stats


def resolve_run_env() -> str:
    if RUN_ENV in {"local", "kaggle"}:
        return RUN_ENV
    if Path("/kaggle/working").exists():
        return "kaggle"
    return "local"


def resolve_out_dir(env: str) -> Path:
    if env == "kaggle":
        return KAGGLE_OUT_DIR
    return LOCAL_OUT_DIR


def main() -> None:
    seed_everything(SEED)
    env = resolve_run_env()
    dataset_root = resolve_dataset_root(DATASET_ROOT, env)
    out_dir = resolve_out_dir(env)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] RUN_ENV     : {env}")
    print(f"[INFO] DATASET_ROOT: {dataset_root}")
    print(f"[INFO] OUT_DIR     : {out_dir}")
    print(f"[INFO] DEVICE      : {DEVICE}")
    if DEVICE != "cuda":
        print("[WARN] CUDA not available. Training will run on CPU and be much slower.")

    frames_root, labels_root = resolve_paths(dataset_root)
    print(f"[INFO] FRAMES_ROOT : {frames_root}")
    print(f"[INFO] LABELS_ROOT : {labels_root}")

    train_items = build_items("train", frames_root=frames_root, labels_root=labels_root)
    val_items = build_items("val", frames_root=frames_root, labels_root=labels_root)
    if not train_items or not val_items:
        raise ValueError("Empty train/val items. Check DATASET_ROOT and whether frames were extracted.")

    train_tf = transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.RandomHorizontalFlip(0.5),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    val_tf = transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    train_ds = DaiseeFrameMultiTaskDataset(train_items, train_tf)
    val_ds = DaiseeFrameMultiTaskDataset(val_items, val_tf)

    sampler = None
    shuffle = True
    if USE_WEIGHTED_SAMPLER:
        # sampler based on engagement imbalance (main task)
        e_labels = [it.engagement for it in train_items]
        cls_w = {k: 1.0 / v for k, v in Counter(e_labels).items()}
        sample_w = [cls_w[it.engagement] for it in train_items]
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

    model = MultiTaskResNet18(dropout=0.2).to(DEVICE)

    if USE_CLASS_WEIGHT_LOSS:
        b_w = inverse_freq_weights([it.boredom for it in train_items]).to(DEVICE)
        e_w = inverse_freq_weights([it.engagement for it in train_items]).to(DEVICE)
        c_w = inverse_freq_weights([it.confusion for it in train_items]).to(DEVICE)
        f_w = inverse_freq_weights([it.frustration for it in train_items]).to(DEVICE)
        crit_b = nn.CrossEntropyLoss(weight=b_w)
        crit_e = nn.CrossEntropyLoss(weight=e_w)
        crit_c = nn.CrossEntropyLoss(weight=c_w)
        crit_f = nn.CrossEntropyLoss(weight=f_w)
    else:
        crit_b = nn.CrossEntropyLoss()
        crit_e = nn.CrossEntropyLoss()
        crit_c = nn.CrossEntropyLoss()
        crit_f = nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, EPOCHS))
    use_amp = torch.cuda.is_available()
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_key = -1.0
    bad_epochs = 0
    history = []
    csv_path = out_dir / "history.csv"
    csv_header = [
        "epoch",
        "train_loss",
        "val_loss",
        "boredom_acc",
        "boredom_macro_f1",
        "engagement_acc",
        "engagement_macro_f1",
        "confusion_acc",
        "confusion_macro_f1",
        "frustration_acc",
        "frustration_macro_f1",
        "avg_macro_f1",
        "lr",
        "gpu_util_pct",
        "gpu_mem_used_mb",
        "gpu_mem_reserved_mb",
        "nvsmi_mem_used_mb",
        "nvsmi_mem_total_mb",
        "gpu_temp_c",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_header)
        writer.writeheader()

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total = 0
        train_loss = 0.0

        for x, y in train_loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast("cuda", enabled=use_amp):
                out = model(x)
                lb = crit_b(out["boredom"], y[:, 0])
                le = crit_e(out["engagement"], y[:, 1])
                lc = crit_c(out["confusion"], y[:, 2])
                lf = crit_f(out["frustration"], y[:, 3])
                loss = W_BOREDOM * lb + W_ENGAGEMENT * le + W_CONFUSION * lc + W_FRUSTRATION * lf

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            bs = y.size(0)
            total += bs
            train_loss += loss.item() * bs

        scheduler.step()
        train_loss /= max(1, total)

        val_m = evaluate(model, val_loader, crit_b, crit_e, crit_c, crit_f)
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_m["loss"],
            "boredom_acc": val_m["boredom_acc"],
            "boredom_macro_f1": val_m["boredom_macro_f1"],
            "engagement_acc": val_m["engagement_acc"],
            "engagement_macro_f1": val_m["engagement_macro_f1"],
            "confusion_acc": val_m["confusion_acc"],
            "confusion_macro_f1": val_m["confusion_macro_f1"],
            "frustration_acc": val_m["frustration_acc"],
            "frustration_macro_f1": val_m["frustration_macro_f1"],
            "avg_macro_f1": val_m["avg_macro_f1"],
            "lr": optimizer.param_groups[0]["lr"],
        }
        row.update(gpu_runtime_stats())
        history.append(row)

        print(
            f"[{epoch:02d}/{EPOCHS}] train_loss={row['train_loss']:.4f} val_loss={row['val_loss']:.4f} "
            f"B_f1={row['boredom_macro_f1']:.4f} E_f1={row['engagement_macro_f1']:.4f} "
            f"C_f1={row['confusion_macro_f1']:.4f} "
            f"F_f1={row['frustration_macro_f1']:.4f} avg_f1={row['avg_macro_f1']:.4f} "
            f"gpu_util={row.get('gpu_util_pct', 'NA')}% "
            f"gpu_mem={row.get('gpu_mem_used_mb', 'NA')}/{row.get('nvsmi_mem_total_mb', 'NA')}MB"
        )
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_header)
            writer.writerow({k: row.get(k, "") for k in csv_header})

        key = (
            0.5 * row["engagement_macro_f1"]
            + 0.2 * row["boredom_macro_f1"]
            + 0.15 * row["confusion_macro_f1"]
            + 0.15 * row["frustration_macro_f1"]
        )
        ckpt = {
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "metrics": row,
            "config": {
                "image_size": IMAGE_SIZE,
                "max_frames_per_clip": MAX_FRAMES_PER_CLIP,
            },
        }
        torch.save(ckpt, out_dir / "last.pt")

        if key > best_key:
            best_key = key
            bad_epochs = 0
            torch.save(ckpt, out_dir / "best.pt")
        else:
            bad_epochs += 1
            if bad_epochs >= PATIENCE:
                print(f"Early stop at epoch {epoch}, best_key={best_key:.4f}")
                break

    (out_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"[OK] saved best: {out_dir / 'best.pt'}")
    print(f"[OK] saved last: {out_dir / 'last.pt'}")
    print(f"[OK] saved history: {out_dir / 'history.json'}")


if __name__ == "__main__":
    main()
