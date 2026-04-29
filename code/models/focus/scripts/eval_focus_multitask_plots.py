#!/usr/bin/env python3
"""
Generate training plots and confusion matrices for DAiSEE multi-task model.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


@dataclass
class FrameItem:
    path: Path
    boredom: int
    engagement: int
    confusion: int
    frustration: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot metrics and confusion matrices for multi-task DAiSEE run.")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("/home/ryh/Thesis/results/focus_multitask_local_e5_tiny"),
        help="Run directory containing best.pt and history.json",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("/home/ryh/Thesis/data/raw/DAiSEE"),
        help="Raw DAiSEE dataset root",
    )
    parser.add_argument("--split", default="val", choices=["val", "train"], help="Split for confusion matrix")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--limit-samples",
        type=int,
        default=0,
        help="Limit number of frame samples for quick eval (0 = all)",
    )
    return parser.parse_args()


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
    if frames_root is None or labels_root is None:
        raise FileNotFoundError(f"Could not resolve frames/labels under {root}")
    return frames_root, labels_root


def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_label_csv(path: Path) -> dict[str, tuple[int, int, int, int]]:
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


def build_items(split: str, frames_root: Path, labels_root: Path) -> list[FrameItem]:
    split_norm = {"train": "train", "val": "val", "validation": "val", "valid": "val"}.get(split.lower(), split.lower())
    csv_name = "TrainLabels.csv" if split_norm == "train" else "ValidationLabels.csv"
    label_map = read_label_csv(labels_root / csv_name)
    split_dir = frames_root / split_norm
    items: list[FrameItem] = []
    for clip_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        label = label_map.get(clip_dir.name)
        if label is None:
            continue
        b, e, c, fr = label
        for p in sorted(clip_dir.iterdir()):
            if p.is_file() and is_image(p):
                items.append(FrameItem(path=p, boredom=b, engagement=e, confusion=c, frustration=fr))
    return items


class FrameDataset(Dataset):
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
        backbone = models.resnet18(weights=None)
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


def macro_f1_from_conf(conf: torch.Tensor) -> float:
    f1s = []
    for i in range(conf.shape[0]):
        tp = conf[i, i].item()
        fp = conf[:, i].sum().item() - tp
        fn = conf[i, :].sum().item() - tp
        denom = 2 * tp + fp + fn
        f1s.append(0.0 if denom == 0 else (2 * tp / denom))
    return float(sum(f1s) / len(f1s))


def plot_history(history: list[dict], out_dir: Path) -> None:
    if not history:
        return
    epochs = [x["epoch"] for x in history]

    plt.figure(figsize=(8, 5))
    plt.plot(epochs, [x["train_loss"] for x in history], label="train_loss")
    plt.plot(epochs, [x["val_loss"] for x in history], label="val_loss")
    plt.xlabel("epoch")
    plt.ylabel("loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "curve_loss.png", dpi=150)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(epochs, [x["boredom_macro_f1"] for x in history], label="boredom_f1")
    plt.plot(epochs, [x["engagement_macro_f1"] for x in history], label="engagement_f1")
    plt.plot(epochs, [x["confusion_macro_f1"] for x in history], label="confusion_f1")
    plt.plot(epochs, [x["frustration_macro_f1"] for x in history], label="frustration_f1")
    plt.plot(epochs, [x["avg_macro_f1"] for x in history], label="avg_f1", linewidth=2.5)
    plt.xlabel("epoch")
    plt.ylabel("macro_f1")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "curve_macro_f1.png", dpi=150)
    plt.close()


def plot_confusion(conf: torch.Tensor, title: str, out_path: Path) -> None:
    labels = ["0", "1", "2", "3"]
    plt.figure(figsize=(5, 4))
    plt.imshow(conf.numpy(), cmap="Blues")
    plt.title(title)
    plt.colorbar()
    plt.xticks(range(4), labels)
    plt.yticks(range(4), labels)
    plt.xlabel("Pred")
    plt.ylabel("True")
    for i in range(4):
        for j in range(4):
            plt.text(j, i, str(int(conf[i, j].item())), ha="center", va="center", color="black")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    out_dir = run_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    history_path = run_dir / "history.json"
    ckpt_path = run_dir / "best.pt"
    if not history_path.exists() or not ckpt_path.exists():
        raise FileNotFoundError(f"Need history.json and best.pt under {run_dir}")

    history = json.loads(history_path.read_text(encoding="utf-8"))
    plot_history(history, out_dir)

    ckpt = torch.load(ckpt_path, map_location="cpu")
    image_size = int(ckpt.get("config", {}).get("image_size", 224))

    frames_root, labels_root = resolve_paths(args.dataset_root)
    items = build_items(args.split, frames_root, labels_root)
    if args.limit_samples > 0:
        items = items[: args.limit_samples]

    tf = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    ds = FrameDataset(items, tf)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    model = MultiTaskResNet18(dropout=0.2)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    confs = {
        "boredom": torch.zeros((4, 4), dtype=torch.int64),
        "engagement": torch.zeros((4, 4), dtype=torch.int64),
        "confusion": torch.zeros((4, 4), dtype=torch.int64),
        "frustration": torch.zeros((4, 4), dtype=torch.int64),
    }

    with torch.no_grad():
        for x, y in dl:
            out = model(x)
            pb = out["boredom"].argmax(dim=1)
            pe = out["engagement"].argmax(dim=1)
            pc = out["confusion"].argmax(dim=1)
            pf = out["frustration"].argmax(dim=1)
            for t, p in zip(y[:, 0], pb):
                confs["boredom"][int(t), int(p)] += 1
            for t, p in zip(y[:, 1], pe):
                confs["engagement"][int(t), int(p)] += 1
            for t, p in zip(y[:, 2], pc):
                confs["confusion"][int(t), int(p)] += 1
            for t, p in zip(y[:, 3], pf):
                confs["frustration"][int(t), int(p)] += 1

    metrics = {}
    for task, conf in confs.items():
        acc = conf.diag().sum().item() / max(conf.sum().item(), 1)
        f1 = macro_f1_from_conf(conf)
        metrics[f"{task}_acc"] = acc
        metrics[f"{task}_macro_f1"] = f1
        plot_confusion(conf, f"{task} Confusion Matrix", out_dir / f"cm_{task}.png")
    metrics["avg_macro_f1"] = sum(metrics[f"{t}_macro_f1"] for t in confs) / len(confs)
    metrics["num_eval_samples"] = len(items)

    (out_dir / "eval_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"[OK] plots saved in: {out_dir}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

