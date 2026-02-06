"""Copy the hand/crib stats DB from crib_engine into crib_back/data."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _default_src(root: Path) -> Path:
    return root.parent / "crib_engine" / "data" / "hand_crib_stats.sqlite"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=str, default=None, help="Source DB path.")
    ap.add_argument("--dst", type=str, default=None, help="Destination DB path.")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    src = Path(args.src) if args.src else _default_src(root)
    dst = Path(args.dst) if args.dst else (root / "data" / "hand_crib_stats.sqlite")

    if not src.exists():
        raise SystemExit(f"Source DB does not exist: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied {src} -> {dst}")


if __name__ == "__main__":
    main()
