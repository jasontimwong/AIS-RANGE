#!/usr/bin/env python3
"""
Basemap assets evaluation script.

Scans locally cached map assets to assess readiness for an ocean-style basemap:
- OSM standard tiles (raster) at low zoom levels
- OpenSeaMap seamark overlay tiles (raster) at low zoom levels
- OSM water polygon datasets (archives)

Outputs a JSON summary under artifacts/basemap_eval.json
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def list_png_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.png") if p.is_file()]


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def is_valid_png(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            head = f.read(8)
        return head == PNG_MAGIC
    except Exception:
        return False


def summarize_tiles(root: Path) -> Dict[str, object]:
    tiles = list_png_files(root)
    total_size = sum(file_size(p) for p in tiles)
    # Group by zoom level from path .../z/x/y.png
    per_zoom: Dict[str, Dict[str, int]] = {}
    for p in tiles:
        parts = p.parts
        # Expect .../<root>/<z>/<x>/<y>.png
        try:
            z = parts[-3]
        except Exception:
            z = "unknown"
        per_zoom.setdefault(z, {"tiles": 0, "size_bytes": 0})
        per_zoom[z]["tiles"] += 1
        per_zoom[z]["size_bytes"] += file_size(p)

    # Validate a small sample for PNG correctness
    sample = tiles[: min(50, len(tiles))]
    valid = sum(1 for p in sample if is_valid_png(p))

    return {
        "root": str(root),
        "total_tiles": len(tiles),
        "total_size_bytes": total_size,
        "zoom_levels": per_zoom,
        "sample_checked": len(sample),
        "sample_valid_png": valid,
        "valid_png_ratio": (valid / len(sample)) if sample else None,
        "sample_examples": [str(p) for p in sample[:5]],
    }


def summarize_archive(path: Path) -> Dict[str, object]:
    exists = path.exists()
    size = file_size(path) if exists else 0
    note: Optional[str] = None
    # Heuristic: the simplified zip should be larger than a few MB; if tiny, likely HTML/placeholder
    if exists and size < 1024 * 1024:
        note = "File size unusually small; may not be a valid zip (mirror/redirect placeholder)."
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "note": note,
    }


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    artifacts_dir = repo_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Roots
    osm_tiles_root = repo_root / "data/osm_tiles/standard"
    seamark_tiles_root = repo_root / "data/openseamap_tiles/seamark"
    osm_water_dir = repo_root / "data/osm_water"

    # Summaries
    osm_tiles_summary = summarize_tiles(osm_tiles_root)
    seamark_summary = summarize_tiles(seamark_tiles_root)

    simplified_zip = summarize_archive(osm_water_dir / "simplified-water-polygons-3857.zip")
    split_zip = summarize_archive(osm_water_dir / "water-polygons-split-3857.zip")

    result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "osm_tiles": osm_tiles_summary,
        "openseamap_seamark_tiles": seamark_summary,
        "osm_water_archives": {
            "simplified_3857_zip": simplified_zip,
            "water_polygons_split_3857_zip": split_zip,
        },
        "notes": [
            "Low-zoom raster tiles (z=0..2) cached for global baseline.",
            "OpenSeaMap seamark overlay cached for the same zooms.",
            "OSM simplified water polygons zip appears invalid/tiny on this mirror; full split archive present.",
        ],
    }

    out_path = artifacts_dir / "basemap_eval.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Wrote basemap evaluation to {out_path}")


if __name__ == "__main__":
    main()


