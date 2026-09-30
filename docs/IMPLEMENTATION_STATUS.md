# Trading OS V2 实现状态

| 层 | V2 基础能力 | 状态 |
|---|---|---|
| Data / Market State | 知识分类、身份、UTC、TTL、skew、未来数据阻断 | 已实现 |
| Regime | 多维对象、进入/维持迟滞、确认次数、TTL | 已实现基础版 |
| Alpha | Trend、Momentum、MeanReversion；其他类型仅注册 | 已实现三种 |
| Arbitration | 校准门槛、同源组上限、freshness decay、分歧惩罚 | 已实现 |
| Risk | ALLOW/REDUCE/BLOCK/FREEZE/KILL、多维检查、原子预留 | 已实现基础版 |
| Portfolio / Intent | 保守权重、现金选项、目标净敞口差额 | 已实现 |
| Execution | LIMIT、PAPER、Gate proposal、TestNet capability gate | 已实现 |
| Event / Ledger | SQLite append-only、哈希链、重放、inbox/outbox、修正 | 已实现 |
| Lifecycle | UNKNOWN、部分成交、撤单竞态、fill 去重 | 已实现 |
| Attribution | timing/slippage/fee 无双计分解、residual | 已实现 |
| Learning | 样本不足、区间、权重提案不自动激活 | 已实现基础版 |
| Governance | 四层边界、mode epoch、能力矩阵、持久 kill | 已实现 |

## 明确未实现

- Breakout、RelativeStrength、OnChain、Catalyst 等 Alpha 只有扩展注册契约，没有实现或绩效声明。
- TWAP、POV、ICEBERG、撤改单等返回不支持。
- 没有 LLM 连接；AI 研究接口不伪装成已接入能力。
- 没有实盘写入能力，且不在 V2 授权范围。
- 合成 fixture 只验证系统闭环，不代表历史回测或盈利能力。
- SQLite 尚未进行多主机负载测试；当前定位是模块化单体。

