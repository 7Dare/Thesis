import argparse
from pathlib import Path
from ultralytics import YOLO


def _default_data_yaml(root: Path) -> Path:
    return root / "data/raw/0.355k_university_yolo_Dataset/0.355k_university_yolo_Dataset/data.yaml"


def parse_args() -> argparse.Namespace:
    root = Path("/home/ryh/thesis")
    parser = argparse.ArgumentParser(description="Evaluate YOLO run with configurable dataset.")
    parser.add_argument("--data", type=Path, default=_default_data_yaml(root), help="Path to data.yaml")
    parser.add_argument("--project", type=Path, default=root / "results", help="Results project dir")
    parser.add_argument("--name", default="yolo_focus_alt", help="Run name under project/")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--device", default="0", help='Device id, e.g. "0" or "cpu"')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path("/home/ryh/thesis")
    data_yaml = args.data if args.data.is_absolute() else root / args.data
    project = args.project if args.project.is_absolute() else root / args.project
    run_dir = project / args.name
    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_yaml}")
    best = run_dir / "weights/best.pt"
    last = run_dir / "weights/last.pt"
    weights = best if best.exists() else last
    if not weights.exists():
        raise FileNotFoundError(f"No checkpoint found in {run_dir / 'weights'}")

    model = YOLO(str(weights))
    model.val(
        data=str(data_yaml),
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
    )


if __name__ == "__main__":
    main()
