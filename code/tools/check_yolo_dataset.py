#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a YOLO dataset from data.yaml.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(
            "/home/ryh/thesis/data/raw/0.355k_university_yolo_Dataset/0.355k_university_yolo_Dataset/data.yaml"
        ),
        help="Path to data.yaml",
    )
    parser.add_argument("--sample", type=int, default=200, help="Max label files to inspect per split")
    return parser.parse_args()


def _load_yaml(path: Path) -> Dict:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("data.yaml is not a mapping")
    return data


def _resolve_dir(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p)


def _check_names(data: Dict) -> Tuple[bool, str]:
    nc = data.get("nc")
    names = data.get("names")
    if not isinstance(nc, int):
        return False, "nc missing or not int"
    if not isinstance(names, list):
        return False, "names missing or not list"
    if len(names) != nc:
        return False, f"len(names)={len(names)} does not match nc={nc}"
    return True, "ok"


def _scan_split(split_dir: Path, sample_limit: int, nc: int) -> Dict:
    out = {
        "images": 0,
        "labels": 0,
        "missing_labels": 0,
        "orphan_labels": 0,
        "bad_lines": 0,
        "out_of_range_cls": 0,
        "out_of_range_box": 0,
        "checked_label_files": 0,
    }
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    img_files = [p for p in split_dir.rglob("*") if p.suffix.lower() in image_exts]
    out["images"] = len(img_files)
    lbl_dir = split_dir.parent.parent / "labels" / split_dir.name
    lbl_files = list(lbl_dir.rglob("*.txt")) if lbl_dir.exists() else []
    out["labels"] = len(lbl_files)

    img_stems = {p.stem for p in img_files}
    lbl_stems = {p.stem for p in lbl_files}
    out["missing_labels"] = len(img_stems - lbl_stems)
    out["orphan_labels"] = len(lbl_stems - img_stems)

    for i, lbl in enumerate(lbl_files):
        if i >= sample_limit:
            break
        out["checked_label_files"] += 1
        for line in lbl.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                out["bad_lines"] += 1
                continue
            try:
                cls_id = int(float(parts[0]))
                x, y, w, h = map(float, parts[1:])
            except ValueError:
                out["bad_lines"] += 1
                continue
            if cls_id < 0 or cls_id >= nc:
                out["out_of_range_cls"] += 1
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 <= w <= 1.0 and 0.0 <= h <= 1.0):
                out["out_of_range_box"] += 1
    return out


def main() -> None:
    args = parse_args()
    data_yaml = args.data.resolve()
    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_yaml}")

    data = _load_yaml(data_yaml)
    base = Path(data.get("path", data_yaml.parent))
    if not base.is_absolute():
        base = (data_yaml.parent / base).resolve()

    print(f"[INFO] data.yaml: {data_yaml}")
    print(f"[INFO] dataset root: {base}")

    ok_names, msg = _check_names(data)
    print(f"[CHECK] names/nc: {msg}")
    if not ok_names:
        raise SystemExit(2)

    nc = int(data["nc"])
    for split in ("train", "val", "test"):
        rel = data.get(split)
        if not rel:
            continue
        split_dir = _resolve_dir(base, str(rel))
        print(f"\n[CHECK] split={split} dir={split_dir}")
        if not split_dir.exists():
            print("  - ERROR: split directory missing")
            continue
        stats = _scan_split(split_dir, args.sample, nc)
        for k in (
            "images",
            "labels",
            "missing_labels",
            "orphan_labels",
            "checked_label_files",
            "bad_lines",
            "out_of_range_cls",
            "out_of_range_box",
        ):
            print(f"  - {k}: {stats[k]}")


if __name__ == "__main__":
    main()
