# S-111 表层流集成（最小模型）
- CSV 列：`time_iso, lon, lat, u_ms, v_ms`
- 采样：最近邻（或双线性）+ 最近时刻
- 影响：
  - 代价场：逆流代价↑，顺流代价↓
  - 速度廓线：`v_ground = v_ship_body + current_projection`
