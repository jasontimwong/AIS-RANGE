# S-164 IHO Test Dataset Subset

This directory contains a subset of the S-164 IHO test dataset for smoke testing.

## Scenarios

### 1. Open Water TSS (scenario1/)
- Traffic Separation Scheme in open waters
- Tests TSS compliance and lane following
- Expected: Route follows correct TSS lane

### 2. Coastal Shallow (scenario2/)
- Navigation in shallow coastal waters
- Tests safety contour adherence
- Expected: Route maintains safe water depth

### 3. Harbor Approach (scenario3/)
- Approach to harbor with restrictions
- Tests speed limits and anchorage avoidance
- Expected: Route respects speed restrictions

## Data Format
- S-57 ENC files (.000)
- S-101 files (.s101) where available
- Catalog files (.CATALOG)

## Usage
Run smoke tests with:
```bash
FEATURE_FLAG_S164=true python ci/run_s164_test.py --scenario open_water_tss --enc-path ci/data/s164_subset/scenario1 --output artifacts/s164
```

## Compliance Threshold
- Minimum pass rate: 95%
- All critical checks must pass
- Planning time < specified limits