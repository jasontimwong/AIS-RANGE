#!/usr/bin/env python3
import json
from pathlib import Path


def test_basemap_eval_report_fields(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    tools_path = repo_root / "tools" / "basemap_eval.py"

    # Import evaluator as module
    import importlib.util
    spec = importlib.util.spec_from_file_location("basemap_eval", str(tools_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore

    # Run main to generate report
    mod.main()

    out = repo_root / "artifacts" / "basemap_eval.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))

    # Basic shape checks
    assert "generated_at" in data
    assert "osm_tiles" in data
    assert "openseamap_seamark_tiles" in data
    assert "osm_water_archives" in data
    assert "natural_earth_like" in data

    ne = data["natural_earth_like"]
    # At least keys exist; presence may be Falsey but structure must be there
    expected_keys = [
        "asia_pacific_land",
        "asia_pacific_bathymetry",
        "asia_pacific_seamarks",
        "world_land_simplified",
        "world_simplified",
    ]
    for k in expected_keys:
        assert k in ne
        entry = ne[k]
        assert set(["path", "exists", "size_bytes", "feature_count", "sample_properties"]) - set(entry.keys()) == set()


