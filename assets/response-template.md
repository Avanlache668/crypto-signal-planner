# 中文输出模板（只填写有证据的项目）

## 候选：{PROJECT}（{TICKER} / {CHAIN}）
核验时间：{UTC_TIMESTAMP} UTC；报价市场：{EXCHANGE/PAIR}；数据延迟：{LIVE/DELAYED/UNKNOWN}；另一个报价来源：{SOURCE}。

**为什么选它**：三条有日期/数据/来源支撑的理由。分别讨论技术结构、产品/生态进展、可验证的流动性/估值；没有的写 unavailable。
**反面论证**：代币供应/解锁、项目安全、宏观相关性、可能的价值捕获缺陷。区分官方声明与实际链上发生。

| 项目 | 条件性计划 |
|---|---|
| 当前可信报价 | {quote or 无法核验} |
| 观察支撑/回踩区 | {verified level or 不提供} |
| 突破观察位 | {verified closed-candle level or 不提供} |
| 当前激活路径 | {回踩/突破/都不激活} |
| 第一止盈参考 | {structural target; not forecast} |
| 第二止盈参考 | {structural target; not forecast} |
| 失效参考位 | {structure-based; not guaranteed fill} |
| 最大计划资金风险 | {amount/% or 无法计算} |
| 最大计划资产配置 | {amount/% or 未知} |
| 模型状态 | {WATCH/CONDITIONAL_WATCH_BUY/...} |
| 执行状态 | NO_ORDER unless independently verified |

**具体触发顺序**：必须先满足什么，何时取消计划，何时再重新分析；不能把条件性买区写成已成交。
**风险收益检验**：注明入场、止损、第一目标、费用假设、净R:R、持仓数量上限（如输入数据齐全）；若<2R则不给买入候选。
**状态变化**：只有确认与上次不同，才生成新事件；其他情况写“无已核验的新交易状态变化”。
**数据引用**：来源 + 观察时间 + URL（按所在宿主引用格式），不要伪造浏览成功。
