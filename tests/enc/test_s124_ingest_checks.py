import json, pathlib as pl
from lib.enc.s124_ingest import ingest_warnings

def test_s124_ingest_minimal():
    data = json.loads(pl.Path("datasets/s124/mock_warnings.json").read_text(encoding="utf-8"))
    feats = ingest_warnings(data)
    cats = {f.category for f in feats}
    assert {"speed_limit","prohibited"} <= cats
    speed_zones = [f for f in feats if f.category=="speed_limit"]
    assert speed_zones and hasattr(speed_zones[0], "speed_limit_kts")
    # 所有要素具备 geometry
    assert all(getattr(f,"geometry",None) is not None for f in feats)
