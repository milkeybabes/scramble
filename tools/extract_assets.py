"""One-time ROM -> PNG + JSON extraction for Scramble (1981)."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scramble_assets import export_assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="Scramble parent ROM zip (or merged ZIP with parent ROMs at root)")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]/"data")
    opts = parser.parse_args()
    result = export_assets(opts.rom, opts.output)
    print("Scramble assets extracted successfully:")
    for k,v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
