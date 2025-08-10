import math, datetime as dt, pathlib as pl
from lib.env.s111_currents import load_s111_csv, sample_current, effective_speed_ms, travel_time_s

def test_s111_effect_on_speed_and_time():
    cur = load_s111_csv("datasets/s111/mock_currents.csv")
    t = dt.datetime.fromisoformat("2025-08-10T01:00:00+00:00")
    u, v = sample_current(cur, lon=0.01, lat=0.01, when=t)
    assert abs(u-1.0)<1e-6 and abs(v-0.0)<1e-6

    base_speed = 3.0  # m/s 船体在水中的航速
    heading = 0.0     # 朝正东
    eff = effective_speed_ms(base_speed, u, v, heading)
    assert eff > base_speed  # 顺流地速应更大

    L = 1000.0  # m
    t_no_current = travel_time_s(L, base_speed, 0.0, 0.0, heading)
    t_with_current = travel_time_s(L, base_speed, u, v, heading)
    assert t_with_current < t_no_current
