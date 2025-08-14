#!/usr/bin/env python3
import json
import asyncio
from pathlib import Path


def test_basemap_status_shape():
    """Validate /basemap/status payload structure by importing the handler and awaiting it."""
    # Import app module without running the server
    import importlib.util
    spec = importlib.util.spec_from_file_location("service_app", str(Path("service/app.py").resolve()))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore

    # Ensure the UI geo dir exists (create minimal asset to trigger availability)
    ui_geo_dir = Path("ui/public/geo")
    ui_geo_dir.mkdir(parents=True, exist_ok=True)
    sample_file = ui_geo_dir / "world-simplified.json"
    if not sample_file.exists():
        sample_file.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    # Call async endpoint function
    payload = asyncio.run(mod.basemap_status())

    assert isinstance(payload, dict)
    for key in [
        "osm_tiles_root",
        "openseamap_tiles_root",
        "osm_tiles_count",
        "openseamap_tiles_count",
        "natural_earth_available",
        "ready",
    ]:
        assert key in payload

    # Ready should be True if Natural Earth assets present even when tiles missing
    if payload.get("natural_earth_available"):
        assert payload["ready"] is True


