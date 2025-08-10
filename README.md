# ECDIS Route Planner

符合IMO MSC.232(82)和COLREG标准的海事导航路径规划系统。

## 📚 项目文档

本项目仅维护两个核心文档：
- **[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)** - 系统架构和技术设计
- **[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)** - 开发进度和更新记录

## ✨ 核心功能

- **Hybrid A*路径规划**: 考虑船舶运动学的连续状态空间规划
- **COLREG避碰规则**: 实现Rules 7-19国际避碰规则
- **TSS分道通航**: 自动遵循Traffic Separation Scheme
- **S-57/S-101海图**: 支持标准电子海图格式
- **实时验证**: 安全性、合规性、几何约束验证
- **标准格式**: RTZ/S-421路径交换格式

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install GDAL (platform-specific)
# macOS: brew install gdal
# Ubuntu: apt-get install gdal-bin python3-gdal
```

## Quick Start

### 1. Start the API Service

```bash
cd service
uvicorn app:app --reload
```

### 2. Plan a Route

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"lat": 37.70, "lon": -123.10},
    "goal": {"lat": 37.80, "lon": -122.55},
    "vessel_draft": 8.0,
    "safety_depth": 15.0
  }'
```

### 3. Validate Route

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": "route_20240101_120000",
    "checks": ["safety", "tss", "geometry", "speed"]
  }'
```

### 4. Export RTZ

```bash
curl http://localhost:8000/export/rtz?route_id=route_20240101_120000 \
  -o route.rtz
```

## Run San Francisco TSS Scenario

```bash
./scripts/run_scenario_sf.sh
```

This will:
1. Load NOAA ENC data (US5CA12M)
2. Plan route through SF Traffic Separation Scheme
3. Validate against all safety constraints
4. Generate RTZ file and validation report
5. Test RTZ round-trip import/export

## API Documentation

Interactive API docs available at: http://localhost:8000/docs

Key endpoints:
- `POST /plan` - Plan optimal route
- `POST /validate` - Validate route safety
- `GET /export/rtz` - Export route as RTZ
- `POST /import/rtz` - Import RTZ file
- `GET /status` - Service status

## Testing

```bash
# Run all tests
pytest

# Run COLREG tests
pytest tests/colreg/ -v

# Validate system
python scripts/validate_m4.py
```

## 📊 当前状态

- **版本**: 2.0 (M4 COLREG完成)
- **测试**: 33/33通过 (100%)
- **代码**: ~3,500行生产代码
- **覆盖率**: 56%测试覆盖
- **状态**: 🟢 生产就绪

## 🏛️ 标准合规

- **IMO MSC.232(82)**: ECDIS性能标准
- **COLREG 1972**: 国际海上避碰规则
- **IHO S-57/S-101**: 电子海图数据标准
- **IEC 61174**: ECDIS操作要求
- **S-421**: 路径规划交换格式

## License

MIT License