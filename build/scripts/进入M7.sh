#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT_DIR"

# 1) 打回退点
TAG="v1.6.0-pre-M7-$(date +%Y%m%d_%H%M)"
git add -A && git commit -m "chore: freeze pre-M7 entrypoint" || true
git tag -a "$TAG" -m "Pre M7 entrypoint"
echo "已打 tag: $TAG"

# 2) 开启 M7 所需的特性开关（其他维持关闭）
python - <<'PY'
import yaml,os
flags={
 "four_d_planner": True,   # 4D 时域规划
 "s104_tides": True,       # 水位/潮汐
 "eta_optimizer": True,    # ETA/窗口优化
 "ukc_plugin": True,       # 结合现有 UKC
}
os.makedirs("config",exist_ok=True)
cfg={"feature_flags": flags}
with open("config/feature_flags.yaml","w",encoding="utf-8") as f:
    yaml.safe_dump(cfg,f,allow_unicode=True,sort_keys=False)
print("feature_flags:",flags)
PY

mkdir -p datasets/s104 docs/{planner4d,eta}
echo "✅ 进入 M7：可按任务清单逐项实现。"