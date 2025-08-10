# UKC（Under Keel Clearance）最小模型
- UKC 定义：`UKC = depth - draft + tide - wave_heave`
- 约束：`UKC >= min_ukc_m`
- 集成：对路线离散采样（含中心浅点），输出最小 UKC 与违例计数
