import csv, numpy as np, pathlib as pl
from lib.enc.s102_adapter import load_s102_csv, to_no_go_mask

def test_s102_no_go_mask_matches_expected(tmp_path):
    grid_p = pl.Path("datasets/s102/mock_s102_grid.csv")
    lon, lat, depth = load_s102_csv(str(grid_p))  # depth shape: (3,3)
    assert depth.shape == (3,3)

    mask = to_no_go_mask(depth, safety_depth_m=10.0)  # True=no-go
    # 读取期望 mask
    rows = []
    with open("tests/fixtures/s102/expected_mask.csv","r",encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("#") or not line.strip():
                continue
            rows.append([int(x) for x in line.strip().split(",")])
    expected = np.array(rows, dtype=bool)
    assert mask.shape == expected.shape
    assert np.array_equal(mask, expected), f"no-go mask mismatch:\n{mask}\nvs\n{expected}"
