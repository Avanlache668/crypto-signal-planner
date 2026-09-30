# Crypto Autonomous Trading OS — FOUNDATIONS V2

版本：2.0 设计提案 · 日期：2026-10-01（Asia/Shanghai）  
状态：供架构评审的规范；不是已实现功能、收益承诺或实盘授权。  
基线：`Avanlache668/crypto-signal-planner`，commit `6845f8e7e72db7a8bbf62524be0de6a7f5763a5b`。

本文独立定义正确抽象，再给出兼容迁移路径。当前交付仅新增本文，不修改脚本、Skill、安装方式、CI 或现有参数。下文 MUST 表示未来实现必须满足；SHOULD 表示有记录理由才可偏离；候选研究项不等于生产能力。

## 1. 系统设计哲学

系统管理的是**有证据的认知、有限的风险承担权和可追溯的经济状态变化**。它不是把一组买卖规则连到交易所的机器人。

> Model proposes. Risk constrains. Execution translates. Ledger records. Learning evaluates. Governance sets limits.

逻辑流水线：Data → Market State → Regime → Alpha → Signal Arbitration → Risk → Portfolio Construction → Intent → Execution Policy → Exchange Adapter → Position Lifecycle → Attribution → Learning → Governance。

这条链描述依赖关系，不是一次性串行审批。Risk 是贯穿候选筛选、组合构建、预算预留、子订单发送和存续仓位的独立控制平面；Governance 约束所有层；Ledger 从第一份数据证据开始记录。Risk 的第一次筛选不代表未来发送已经获准。

核心原则：

- **证据分层**：观测、确定性派生、推断使用不同类型，缺失是缺失，未知不是零。
- **确定性核心**：相同输入、逻辑时钟、政策版本、数值实现和事件序列，产生相同数值及决策结果。
- **非确定性隔离**：AI 可以提炼新闻、提出情景、生成待验证假说；不计算最终仓位、风险、资金、手续费和账本，不拥有执行凭据。
- **能力而非口头约束**：没有 capability 的组件无法创建外部副作用；策略和学习模块没有交易所写入权限。
- **fail closed**：不确定时停止增加风险，保留记录、对账和有条件的风险处置能力；不把盲目平仓称为安全。
- **长期演化**：先模块化单体和显式契约，再按可靠性需要拆服务；不先引入分布式系统复杂度。

### 1.1 责任与所有权

| 模块 | 拥有的决定 | 不拥有的决定 |
|---|---|---|
| Data / Market State | 数据来源、身份、时间与知识分类 | 是否交易 |
| Regime | 多维环境判断和转换证据 | 仓位数量 |
| Alpha | 条件机会及失效条件 | 风险许可、订单类型 |
| Arbiter | 候选合成、分歧和弃权 | 最终分配、资金授权 |
| Risk Governor | 约束、风险上限、预算预留、熔断 | 伪造交易观点 |
| Portfolio Constructor | 约束内的目标敞口 | 修改风险限制 |
| Intent Compiler | 目标到经济动作的转换 | 指定交易所订单报文 |
| Execution / Adapter | 受限执行计划、场所协议转换 | 增加目标敞口或放宽约束 |
| Ledger / Lifecycle | 实际经济变化、核对与状态投影 | 把提案认作成交 |
| Learning / Governance | 评估建议 / 有权限的版本生效 | 学习直接修改安全规则 |

## 2. 核心对象定义

### 2.1 公共语义

所有对象携带 `id, schema_version, created_at, run_id, mode, policy_version, provenance_refs`。ID 与哈希分工不同：ID 标识实体，哈希证明规范化内容是否相同；哈希本身不是签名、授权或事实真实性证明。

- `AssetId` 使用链、合约地址或明确的原生资产命名空间，不能只有 ticker。
- `InstrumentId` 增加现货/永续等产品类型、base、quote、settlement、乘数；场所 symbol 是 Adapter 的映射。
- `Money` 必须标记币种；`Quantity` 标记单位；`Return` 标记期间；波动率标记估计窗口和年化惯例。
- 资金、数量、价格、费用使用 Decimal 或固定点及显式精度；风险统计可以使用固定库/求解器版本的受控浮点，固定容差、排序、线程/种子设置。不得宣称跨任意硬件天然逐位一致。
- 交易时间采用 UTC，展示可本地化；`event_time`、`received_at`、`available_at`、`decision_at` 不可混用。历史决策只能读取当时已 available 的信息。
- 不可用值为 `null + missing_reason`；拒绝 NaN、Infinity、单位冲突和无版本枚举。

### 2.2 MarketState：截至某时刻的可验证认知快照

“完整”指字段、来源、依赖和未知范围都显式呈现，不意味着系统掌握世界的全部事实。

```text
MarketState {
  state_id, as_of, knowledge_cutoff, universe_version,
  observed: Observation[], derived: DerivedFact[], inferred: Inference[],
  field_quality, source_disagreement, completeness,
  input_refs, content_hash, schema_version
}
Observation { field, value, unit, source_id, source_event_id,
  event_time, received_at, available_at, valid_until, raw_payload_hash,
  quality_flags, epistemic_type: OBSERVED }
DerivedFact { field, value, unit, input_refs, transform_version,
  window, cutoff, valid_until, quality_flags, epistemic_type: DERIVED }
Inference { claim, alternatives, evidence_refs, model_version,
  generated_at, valid_until, uncertainty, calibration_ref,
  epistemic_type: INFERRED }
```

Observed 表示“来源报告了什么”，不保证报告客观真实。新闻源声称解锁发生是观测到一条报道；解锁是否实际发生仍需链上证据。Derived 是可重算转换，继承最弱依赖的数据质量；不能通过公式洗白推断。Inferred 可以由 AI 或统计模型产生，持有独立推断标签。

| 字段族 | 典型分类 | 必须附带的上下文 |
|---|---|---|
| price / orderbook | 报价、成交、深度快照为 Observed | 场所、序列、买卖侧、交易对、时间；book 缺口需重新同步 |
| volume | 原始逐笔为 Observed，窗口聚合为 Derived | base/quote 单位、窗口、覆盖率、是否仅单场所 |
| volatility / liquidity | 历史估计、spread/depth 指标为 Derived；未来冲击为 Inferred | 估计方法、价格来源、数量档位、置信区间 |
| funding / basis / open interest | 结算记录/持仓报告为 Observed，基差为 Derived，预测资金费为 Inferred | 合约类型、结算周期、OI 单位、现货对应关系 |
| BTC regime / cross-asset | 指标为 Derived，状态判断通常为 Inferred | BTC 状态引用、共同时间截面、相关窗口 |
| macro / catalyst | 发布记录为 Observed，影响判断为 Inferred | 发布时间、修订 vintage、预定与实际时间 |
| token supply | 合约/供应报告为 Observed，汇总为 Derived，未来流通影响为 Inferred | 流通口径、归属计划版本、链及最终性 |
| freshness / disagreement / confidence | 质量计算为 Derived，可靠性判断可为 Inferred | 字段级 TTL、质量原因、校准来源 |

每个消费模块声明 `DataRequirement(required_fields, max_age, max_skew, allowed_quality, fallback_policy)`。快照不必所有字段同时更新，但必须满足消费者时序偏差约束。缺 funding 的现货研究可继续；需要 funding 的 Alpha 必须弃权，不能补成 0。

来源冲突保留各自事实及差异，不无条件取平均。先排查资产、单位、场所与时间错配，再按版本化规则选择或隔离。价格关键源冲突超阈值：BLOCK 新风险；现有仓位采用保守估值区间并继续核对。禁止用大模型“综合判断”的单值替代冲突证据。

`confidence` 不设计为一个万能数字：分别保存数据完整性、来源可靠性、预测概率和模型不确定性。数据新鲜不代表预测正确；LLM 自评 0.9 不等于 90% 胜率。

### 2.3 Regime：层级作用域 × 正交维度

```text
RegimeAssessment {
  assessment_id, scope_type, scope_id, dimension, label,
  posterior_or_score, calibration_ref, evidence_refs,
  entered_at, evaluated_at, valid_until, previous_id,
  transition_rule_version, status: ACTIVE | UNCERTAIN | STALE | UNKNOWN
}
```

| 层 | 作用域与标签示例 |
|---|---|
| MacroRegime | 全球/经济体：RISK_ON、RISK_OFF、UNCERTAIN |
| CryptoRegime | 加密市场：扩张、去杠杆、分化 |
| AssetRegime | 单资产趋势：TREND_UP、TREND_DOWN、RANGE |
| LiquidityRegime | 市场/场所/资产：NORMAL、LOW_LIQUIDITY、DISLOCATED |
| VolatilityRegime | 市场/资产：VOL_EXPANSION、VOL_CONTRACTION、STABLE |
| EventRegime | 资产/行业：EVENT_RISK、POST_EVENT、NO_KNOWN_EVENT |

`RISK_ON + TREND_UP + VOL_EXPANSION + LOW_LIQUIDITY + EVENT_RISK` 合法且有意义。父层是条件上下文，不以一票覆盖子层；宏观 risk-on 与某币下跌也不矛盾。同一作用域、同一维度的互斥标签需要保留概率分布或标为 UNCERTAIN，不能同时硬判真。

转换规则 MUST 版本化：进入阈值高于维持阈值、最短驻留期、连续确认次数及紧急越级条件共同构成 hysteresis。TTL 到期产生 STALE，禁止无限沿用旧标签。紧急流动性断裂可绕过驻留期收紧风险；宽松恢复必须经过确认期。阈值应在训练外验证，本文不虚构通用有效数值。

### 2.4 Alpha：标准化预测容器，不是交易许可

```text
AlphaSignal {
  alpha_signal_id, alpha_id, alpha_version, asset, instrument_scope,
  direction: LONG | SHORT | FLAT, score, score_semantics,
  confidence: {kind, value, calibration_ref}, horizon, expiry,
  regime_dependency, evidence, invalidation,
  prediction: {kind, target, unit, reference_price, horizon,
               expected_return?, quantiles?, probability?, event_definition?,
               rank?, universe_id?, cost_basis},
  state_id, dependence_group, emitted_at
}
```

类型注册表包括 Trend、Breakout、Momentum、MeanReversion、RelativeStrength、CrossSectional、Volume、Liquidity、OnChain、Catalyst、Macro、SupplyUnlock、Sentiment。类型只定义研究家族，不给予权限。SHORT 在当前现货模式只能作为减仓证据，不能建立负库存。

**决策：prediction 为总容器；expected_return 为已校准模型的优选组合输入；rank/probability 为有明确语义的可选输出；utility 属于组合层。**

| 输出 | 有用之处 | 不可直接做的事 |
|---|---|---|
| expected_return + 分布/区间 | 同一期间内比较经济边际 | 忽略估计误差、直接乘资金 |
| probability | 如“24h 净收益大于 0”的概率 | 把胜率当收益大小；忽略亏损尾部 |
| rank | 横截面相对机会 | 把第一名当正收益、跨 universe 比分 |
| score | 模型内部排序 | 跨 Alpha 直接平均 |
| utility | 反映组合风险与成本偏好 | 让 Alpha 私自决定系统风险厌恶 |

不同 horizon 先分桶，不用机械年化强行拼接；分数到收益的映射必须有冻结的样本外校准器。无校准的叙事 Alpha 最多作为 WATCH 或明确受限的证据特征，不能被自动包装成可配置资金的收益预测。基础收益预测默认 gross，成本由统一成本模型扣除一次。

### 2.5 Signal Arbitration

输出 `ArbitratedSignal{signal_id, state, horizon_bucket, aggregate_prediction, confidence, disagreement, included_refs, excluded_refs_with_reasons, regime_refs, model_version, expiry}`。

处理顺序：身份/过期验证 → 冲突检测 → regime conditioning → 校准 → 依赖分组与相关折扣 → freshness decay → 分歧惩罚 → 确定性合成/弃权。

- **veto 分两类**：Arbiter 的证据 veto 排除失效或不适用信号；Risk 的授权 veto 禁止承担风险。Alpha 不能发出能覆盖全局 Risk 的 veto/许可。
- **V2 默认**：在相同预测目标内使用版本化加权 ensemble；权重来自冻结校准集，依赖组设总权重上限。来自同一行情源的 RSI、动量、突破不算三份独立证据。
- **Freshness**：`decay = exp(-ln(2) × age / half_life)` 仅在 TTL 内生效，到期权重为零；age 使用实际逻辑时钟，不能用重生成报告时间刷新旧证据。
- **Disagreement**：保留方向冲突和收益分布差异，降低候选置信度或弃权。不能将相反意见平均为“高置信中性”。
- **Bayesian aggregation**：V3 候选；仅在似然、先验、依赖结构可验证时启用。禁止把多个概率相乘并假设天然独立。
- **Calibration**：可靠性图、Brier/log loss 按 horizon 与 regime 评估；未经样本外检验的置信度只标 RAW。分类校准方法不直接证明金融收益预测有效。

| 状态 | 严格语义 |
|---|---|
| NO_ACTION | 当前没有足够经济行动依据；保留原因 |
| WATCH | 证据未完成或未校准 |
| WATCH_BUY | 买入条件尚未成立 |
| BUY_CANDIDATE | 可进入风险和组合评审，不等于获准交易 |
| REDUCE_CANDIDATE | 建议降低已有敞口 |
| EXIT_CANDIDATE | 建议目标敞口归零 |

## 3. 状态机

### 3.1 Position：经济事实与工作流正交

单一枚举会把“部分成交但已经有风险”误认为未持仓。因此权威状态拆成：

- `economic_status: FLAT | EXPOSED | CLOSED`，由经核验 fills、费用、调整与账本计算。
- `workflow_status: PROPOSED | PENDING_ENTRY | PARTIALLY_FILLED | OPEN | SCALE_IN | REDUCING | EXIT_PENDING | CLOSED | INVALIDATED`。
- `thesis_status: VALID | INVALIDATED | UNKNOWN`。
- `reconciliation_status: CONFIRMED | PENDING | DISPUTED`。

| 当前工作流 | 事件与条件 | 下一状态 / 经济后果 |
|---|---|---|
| PROPOSED | Intent 获准且 entry 计划开始 | PENDING_ENTRY；仍可能零持仓 |
| PROPOSED / PENDING_ENTRY | 撤销/失效，确认无成交、无未决订单 | INVALIDATED；FLAT |
| PENDING_ENTRY | 首次非零但未足额 fill | PARTIALLY_FILLED；立即 EXPOSED 并承担风险 |
| PENDING_ENTRY / PARTIALLY_FILLED | 达成目标，或确认余单终止且留仓 | OPEN；按实际量记账 |
| OPEN | 新增仓 Intent 通过全部门控 | SCALE_IN；新预算单独预留 |
| SCALE_IN | 完成或确认终止增仓 | OPEN；保留实际成交 |
| OPEN / PARTIALLY_FILLED / SCALE_IN | 减仓计划启动 | REDUCING；先处理可能增加敞口的余单 |
| EXPOSED 对应工作流 | 退出意图通过处置约束 | EXIT_PENDING；仓位仍然存在 |
| REDUCING | 完成部分减仓且核对剩余量 | OPEN |
| EXIT_PENDING | 库存为零、无活跃/未知订单、费用核对完成 | CLOSED；计算最终归因 |
| 任意有库存状态 | thesis 失效 | thesis=INVALIDATED；发退出候选，不抹除库存 |

部分入场后失效不能简单进入终态 INVALIDATED；先记录事实并启动处置。小额 dust 仍是敞口，不能四舍五入为 CLOSED；若有合法会计调整，必须单独有证据的 adjustment 事件。CLOSED 后重新建仓创建新 position ID；迟到成交先记账并进入 DISPUTED/恢复敞口流程，不能因已 CLOSED 丢弃真实事件。

Position 必须关联 originating signal IDs、alpha IDs、regime snapshot、预算分配与消耗、intent IDs、order IDs、fill IDs、lot IDs、归因版本。交易所净头寸和策略虚拟子仓位分开；虚拟仓位之和必须与核对后的实际库存一致，无法分配部分进入 suspense。

### 3.2 Order 与 Intent 生命周期

Intent：`DRAFT → VALIDATED → RESERVED → ACTIVE → COMPLETED`；另有 REJECTED、EXPIRED、SUPERSEDED、CANCELLED。EXPIRED 禁止继续发子单，但不证明旧订单已经撤掉。更改目标产生新版本并 supersede，保留因果链。

Order：`PROPOSED → READY → SEND_PENDING → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED`；分支 REJECTED、CANCEL_PENDING、CANCELLED、EXPIRED、UNKNOWN。撤单请求成功发送不等于撤单已确认；CANCEL_PENDING 仍接收 fills。撤单确认后仍可能收到迟到的历史 fill；按成交 ID 去重并核对数量。

网络超时进入 UNKNOWN，保留最坏风险和资金锁定，先查询订单/成交/余额对账。没有唯一证据证明请求未被接受，不重发新的经济动作。

### 3.3 Operating Mode 与运行健康状态

模式固定为 RESEARCH、SHADOW、PAPER、TESTNET、LIVE_PROPOSAL。另有正交健康状态 `RUNNING | DEGRADED | FROZEN | KILLED | RECOVERING`，不能用切模式解除 kill。

模式转换：请求 → 校验权限/矩阵 → 停发并隔离未完成命令 → 对账 → 重算预算 → 记录 MODE_CHANGED → 激活新 mode epoch。旧 epoch 的执行计划、capability token 与未发命令全部失效。不同模式账本、账户、预算和凭据隔离；TestNet 仓位不能变成实盘仓位。

## 4. 事件模型与重放

### 4.1 Envelope 与存储

```text
Event {
  event_id, event_type, schema_version, aggregate_type, aggregate_id,
  aggregate_version, stream_sequence, run_id, mode, mode_epoch,
  occurred_at, recorded_at, available_at, logical_time,
  producer, causation_id, correlation_id, idempotency_key,
  policy_version, model_version?, input_refs, payload,
  previous_hash?, content_hash
}
```

权威 domain log append-only；原始大体积行情可置于不可变对象存储，由哈希及保留策略引用。仅保存摘要不足以重算，需要保证所需原始数据可取回。机密不入事件；保存脱敏证据和 secret reference。哈希链用于发现篡改，仍需要权限控制、备份及外部可信检查点。

`Event → pure Reducer → Current State`。Reducer 不联网、不读真实时钟、不调用 AI、不发送订单。快照是优化，必须带最后 sequence、版本和 hash；可删除后从有效事件重建。

每个 aggregate 顺序严格递增，通过 expected version 防并发覆盖；不伪造跨所有源的天然全序。涉及账户预算的事务由单一串行所有者或可串行化事务处理。跨账户/服务使用显式 saga 与保守占用，不能借最终一致性超卖预算。

### 4.2 事件词汇

| 类别 | 必备事件 |
|---|---|
| 认知 | MARKET_STATE_UPDATED、REGIME_CHANGED、DATA_STALE、SOURCE_DISAGREEMENT |
| 候选 | ALPHA_EMITTED、SIGNAL_CREATED、SIGNAL_REJECTED |
| 风险 | RISK_EVALUATED、RISK_BLOCKED、BUDGET_RESERVED、BUDGET_COMMITTED、BUDGET_RELEASED、BUDGET_REVALUED、KILL_SWITCH_TRIGGERED |
| 组合/意图 | PORTFOLIO_TARGET_CHANGED、INTENT_CREATED、INTENT_EXPIRED、INTENT_SUPERSEDED |
| 执行 | ORDER_PROPOSED、ORDER_SEND_REQUESTED、ORDER_SENT_TESTNET、ORDER_ACKNOWLEDGED、ORDER_REJECTED、ORDER_STATUS_UNKNOWN、ORDER_CANCEL_REQUESTED、ORDER_CANCELLED、ORDER_FILLED |
| 仓位/账本 | POSITION_OPENED、POSITION_CHANGED、POSITION_CLOSED、LEDGER_POSTED、RECONCILIATION_COMPLETED、RECONCILIATION_FAILED、CORRECTION_RECORDED |
| 评估/治理 | MODEL_EVALUATED、WEIGHT_UPDATE_PROPOSED、WEIGHT_UPDATED、POLICY_ACTIVATED、MODE_CHANGED、RECOVERY_AUTHORIZED |

ORDER_FILLED 表示有特定数量的经核验成交事实，可发生多次，不暗示整张订单全部成交；必须携带 venue/account/order/trade ID、数量、价格、费用币种和 provenance。PAPER 的模拟成交同名时必须有 `fill_origin=SIMULATED` 和 simulator_version；禁止报成交易所成交。ORDER_SENT_TESTNET 只证明已发送，不证明接受或成交。V2 没有实盘发送事件路径。

### 4.3 副作用可靠性

接受命令、预留预算、写入 domain event 与 outbox 必须原子提交。Dispatcher 在实际发送前再次检查 mode epoch、capability、有效期、风险版本与预算。外部 API 无法加入本地事务，不能承诺端到端 exactly-once。

使用 inbox 去重、稳定 client action ID、状态核对和重试策略实现经济动作不重复。交易所自定义 ID 不自动等于强幂等键，具体语义须由 Adapter conformance 测试证明。发送后进程崩溃、尚未落回执：恢复时查询外部事实，保持 UNKNOWN，不盲目再发。

重放默认禁止 dispatcher，全部外部写能力为空；AI 原输出按事件重放，不重新生成。重新跑新模型属于新 run 的研究实验，不属于恢复。数据修订/链重组以更正事件记录，不覆写历史；分别提供“当时所知”与“现已修正”视图。

## 5. Risk Budget：系统的稀缺资源

### 5.1 是共同资源语言，不是单一万能货币

名义本金不是风险预算。建议主预算采用基准货币计价的压力损失容量，并保留不能互换的多维硬约束：

```text
RiskBudget {
  budget_id, scope, base_currency, valuation_snapshot_id, model_version,
  stress_loss_limit, volatility_limit, gross_exposure_limit,
  asset_limits, cluster_limits, venue_limits, liquidity_limits,
  daily_loss_limit, weekly_loss_limit, drawdown_limit,
  reserve_buffer, allocations, reservations, valid_until, policy_version
}
```

不能用未耗尽的波动率预算抵消交易所集中风险，也不能把每日亏损额度解释为保证最大损失。VaR、ES、止损距离或压力情景均不提供绝对损失上界。

对各压力情景 s 定义 `L_s(P)=max(0, -PnL_s(P))`，`R(P)=max_s L_s(P)`；PnL_s 包括统一的 gap、退出冲击、费用和 FX 假设。每次候选交易必须检查 `R(P + pending + proposal)` 及其他所有硬约束。

V2 保守做法：为每笔增加敞口计算非负 stand-alone 压力占用，并加总预留；同时运行组合情景检验。未经认证不提前兑现分散或对冲收益。V3 可以采用有版本的净组合边际风险，但必须处理非线性、共同尾部、路径依赖和模型误差。

### 5.2 预算账本与并发

```text
capacity = used + reserved + available + buffer
available = max(0, capacity - used - reserved - buffer)
breach = max(0, used + reserved + buffer - capacity)
```

第一行仅在未超限时是分解恒等式；超限时 available 为零，breach 单独显示，禁止通过把 used 截断来“守恒”。预算占用随市场重新估值，既不是永久固定 token，也不等于实际亏损。

申请 → 原子预留 RESERVED → 确认 fill 后按实际敞口转 USED → 余量继续 RESERVED → 确认无在途/活跃订单后释放。预留 TTL 只触发核对，不自动释放可能已发到交易所的未知订单。取消请求、掉线、Intent 过期都不能直接回收预算。

目标组合中的探索分配不等于真实预留；只有有效意图在发送前获得 reservation。替换订单不能双花释放出的额度；多个策略、多个 worker 共享账户级序列/事务门控。

**示例仅检验模型，不是参数建议**：capacity=1,000、used=300、reserved=200、buffer=100，则 available=400。A 请求250与B请求200并发，A先获准后B只能获得150上限或被拒绝。A部分成交对应100风险占用，则 used=400、reserved=350（原200+余150），available仍为150。确认撤掉A余单后reserved=200，available=300。波动跃升导致used=900时，900+200+100超限200，available=0并收紧风险。

### 5.3 风险度量约定

日/周损失和 drawdown 采用经外部现金流调整、含已实现与未实现PnL及费用的权益序列，明确 UTC 截点、周起点、高水位版本和估值来源。充值不重置回撤；提币不误报交易亏损。政策变更不自动清零熔断状态。价格缺失时展示区间/未知并冻结增加风险，不继续以旧净值扩大额度。

## 6. Alpha 与 Risk 的边界

RiskDecision 为 `decision, scope, allowed_actions, maximum_exposure, risk_constraints, reservation_ref, reason_codes, evidence_refs, evaluated_at, valid_until, policy_version`。授权绑定具体候选/目标哈希、账户及模式，不能复制给其他交易。

| 决策 | 语义与允许动作 |
|---|---|
| ALLOW | 在明确上限内允许，发送前仍需复核 |
| REDUCE | 限缩提案额度/目标；必要时另发风险处置 Intent，不代表随意市价卖出 |
| BLOCK | 拒绝当前候选或动作；不自动取消其他合法订单 |
| FREEZE | 作用域内停增仓、禁止新风险；继续核对，按能力取消风险增加型挂单；处置另行审核 |
| KILL | 持久锁存，禁普通执行；仅独立授权的应急路径可核对、撤单或受限减仓，绝不自动解锁 |

同时命中的风险规则取 allowed_actions 的交集、数值上限的最紧值；枚举严重度用于展示，不能代替动作权限计算。trade、asset、portfolio、liquidity、volatility、correlation、drawdown、daily/weekly loss、event、exchange、data、model risk 均为独立可审计规则。

三个门：候选预筛选 → 对最终 TargetPortfolio 完整评估并预留 → 每个子订单发送前即时复核。仓位存续期间持续重估；Risk 可主动提出减仓，不必等待 Alpha 变空。

Alpha 无法提高预算或解释掉风险拒绝。减仓也可能产生滑点、反向开仓或破坏对冲，必须核验库存和组合后果；当前现货卖出数量不能大于已核对的可用库存。KILL 不保证外部订单已撤或风险已消失，状态报告必须展示残留风险。

## 7. Intent 与 Order 的边界

```text
TradeIntent {
  intent_id, intent_version, portfolio_target_id, asset, instrument_scope,
  action: ENTER | INCREASE | REDUCE | EXIT | REBALANCE,
  side, desired_exposure: {target_value, unit, valuation_ref},
  urgency, max_slippage: {bps, reference_price_id}, price_constraint,
  time_horizon, expiry, risk_budget_ref, reservation_ref,
  reason, signal_refs, regime_refs, invalidation,
  mode, mode_epoch, policy_version, content_hash
}
```

desired_exposure **统一指完成后的目标净敞口**，不是本单数量。delta 由当前经核对库存、已经成交及未完成意图共同计算；价格变化后不能重复把完整目标当增量买入。可采用 base quantity 或基准货币目标，但必须明确单位及估值时间。side 由目标差额推导并与 action 一致校验。

Intent 不含 Gate symbol、endpoint、API key、交易所 order ID，也不指定 LIMIT/TWAP。一个 Intent 可对应多计划版本、多子订单和多 fills；执行策略变更不改变经济目标。max_slippage 是约束，不能保证最终成交；无法满足时暂停/返回不可行，不私自放宽。

风险处置意图 `origin=RISK` 可以没有 Alpha，但仍关联被处置 position、风险原因和治理授权，归因链的空 Alpha 必须有原因。所有订单必须追溯到 Intent，包括手工导入订单使用的 `EXTERNAL_ORIGIN` 记录；不得倒填伪造策略原因。

## 8. Portfolio 架构

`TargetPortfolio{target_id, account_scope, as_of, horizon_bucket, target_exposures, cash_target, valuation_ref, input_signal_refs, covariance_version, cost_model_version, constraints_hash, solver_version, diagnostics, expiry}`。

输入：候选净经济优势、校准不确定性、相关性、波动、流动性、现有库存、所有 pending commitments 和风险预算。输出是目标，不是交易指令。现金是合法分配结果；无足够优势时允许全现金或保持现有仓位。

规范化目标可表述为：

`max_w  μᵀw − λ/2 · wᵀΣw − C(w−w_current) − U(w)`

在预算、现金、gross/net、资产/簇/场所、流动性、周转和模式约束下求解。μ、Σ、C、U 必须同一时间范围和收益单位；U 是对估计误差的保守惩罚。已有挂单以最坏成交结果进入可行性检查。不要把置信度同时重复折进 μ、U 和权重而不记录含义。

| 方法 | V2 取舍 |
|---|---|
| Risk parity | 缺可靠收益预测时的研究基线，不是自动配置所有币的理由 |
| Volatility targeting | 仅在授权上限内缩放，估计波动下降不能自动突破杠杆/敞口上限 |
| Marginal risk contribution | `MRC_i=(Σw)_i/σp`，`RC_i=w_i MRC_i`；σp>0且协方差合法时使用 |
| Conviction weighting | conviction 必须可校准，设上限和不确定性收缩 |
| Fractional Kelly | 仅作研究候选；小收益近似 μ/σ²不是通用配仓公式。分布、尾部、成本和样本不足时禁用；即便启用也受全部硬约束 |
| Altcoin clustering | 相关矩阵收缩/稳定化，结合行业、链、共享抵押品和共同流动性；簇预算防止表面分散 |

V2 优先简单可审计的受约束分配，复杂优化是可替换插件。协方差不PSD、求解器超时、估计缺失或舍入后不可行：不增仓；输出明确 INFEASIBLE 并把现有超限交给 Risk 处置，不能误把“保持持仓”称为安全。

目标到可执行数量需在舍入、最小订单和费用后再次检验资金与风险；无法执行的 dust 标明。组合 construction 不调用交易所。

## 9. Execution 架构

`ExecutionPlan{plan_id, version, intent_ref, policy_version, algorithm, schedule, child_constraints, cost_estimate, fill_model_ref, venue_candidates, expires_at, replan_triggers, fallback_policy}`。

Execution 优化完成目标所需成本、风险和完成概率，不能重新选择投资观点。输入包括 spread、各档 depth、impact、maker/taker fee、fill probability、latency、cancel ratio、fill ratio、adverse selection。fill probability/impact 是估计，必须保留模型与误差；实际数量和费用由 fill ledger 认定。

| 策略词汇 | 作用 | 约束 |
|---|---|---|
| LIMIT | 价格界限 | 不保证成交；现有 TestNet 实现范围 |
| POST_ONLY | 尽量提供流动性 | 由场所支持及参数验证决定；拒单不自动改 taker |
| TWAP | 时间切片 | 不能因为落后计划突破滑点/预算 |
| POV | 随市场真实成交量参与 | volume 不可靠即暂停，不以自身量自激 |
| ICEBERG | 隐藏或拆分展示量 | 原生/合成语义明确，不能假定每个场所支持 |
| PASSIVE_REPRICE | 受限撤换挂单 | 撤单确认与迟到成交核对，限频、限撤单比 |

以上是未来可表达的计划类型；V2 文档不宣称已有实现。Adapter 声明 CapabilityDescriptor，包括产品、账户、order types、精度、最小量、TIF、撤改语义、查单范围、限频及测试证据。有效能力为系统模式 ∩ 账户权限 ∩ 风险许可 ∩ Adapter 已认证能力，未知即拒绝。

策略层只认识规范化 Instrument；Gate/Binance/Coinbase/OKX 的协议差异留在 Adapter，经济语义不可被“统一接口”掩盖。不支持的功能返回 UNSUPPORTED，不静默降级。涉及不同结算币、合约乘数或保证金，必须先升级领域模型，不能只换 URL。

当前 Gate 集成的真实能力边界仍是 live-readonly 与 TestNet spot LIMIT；LIVE_PROPOSAL 只生成 proposal。本文不新增实盘取消或应急卖出端点。未来撤改功能同样需要独立能力验收。订单 manifest 应逐步绑定完整 Intent、policy、mode、expiry 与输入哈希，而非将现有 payload SHA-256 误称为可执行授权。

## 10. Attribution 模型

### 10.1 先对账，再解释

权威账本记录各币种库存与现金，采用平衡分录和明确估值科目；所有手续费、rebate、资金费、FX、外部资金流与更正独立入账。内部 lot method（如 FIFO）必须版本化，不能随报告改变。

链路为 `PnL → asset → position/lot → fills → orders → intents → arbitrated signals → alpha contributions → regime snapshot`。signal 与 intent 是多对多，不强行制造单一来源。分配规则在决策时冻结且贡献权重和为1；无法归属的残差进入 residual/suspense，不隐藏。按 Alpha 的权重分摊是会计约定，不是因果证明。

基准币权益一致性：`TradingPnL = EndingEquity − StartingEquity − NetExternalFlows`。包含已实现、未实现和费用；估值残差、缺价格和争议余额单列。币种转换使用同一已记录估值快照。

### 10.2 无双计的执行分解

对于同一参考市场、同一计价币、线性现货的一段 signed fill q（买为正，卖为负），定义 decision mid p_d、release mid p_r、fill price p_f、评估价 p_H：

```text
benchmark_component = q × (p_H − p_d)
timing_cost         = q × (p_r − p_d)
slippage_cost       = q × (p_f − p_r)
execution_pnl       = −timing_cost − slippage_cost
net_marked_component = benchmark_component + execution_pnl − fee_cost
```

费用正值为成本、返佣为负；slippage 可为负改善。完整组合必须另外纳入起始库存、各次现金流、FX与资金费，不能把单笔示例直接冒充全账户PnL。多币种或非线性合约另设模型。

这里 alpha PnL 定义为已分配经济动作按 decision 基准价执行的 hypothetical component，不代表纯因果 alpha。spread/impact/adverse selection 可进一步研究，但不得与已计入的 slippage 重复相减。

### 10.3 风险覆盖与机会成本是反事实

Risk overlay impact = 同一冻结策略在“有该风险覆盖”与“去掉指定覆盖”的配对模拟表现差。它不进入真实资金账本，也不能直接等于“避免的损失”。被阻止的交易必须当时就记录候选、截止时间、评估窗口和可成交假设，不能事后只挑大跌案例。

Opportunity cost 基于未成交量与预先指定基准；未成交不一定本可成交，结果需报告模拟成本和区间。Risk 阻止了什么损失应回答：“在指定反事实假设下估计避免X，同时放弃Y收益，覆盖N次案例，存在Z不确定性”，不能伪装为已实现收益。

“为什么赚钱/亏钱”分开回答：账本经济贡献、执行成本、regime 条件表现、模型误差与尚不能识别的因果因素。“哪个 Alpha 有效”依赖样本外、扣费、独立样本和替代模型对照，而非分摊PnL排行榜。

## 11. Learning 模型

```text
AlphaPerformance {
  alpha_id, version, regime, horizon, evaluation_window,
  sample_count, effective_sample_count, expectancy, confidence_interval,
  Sharpe, max_drawdown, hit_rate, calibration,
  turnover, cost_adjusted_return, coverage, decay_estimate,
  selection_bias_notes, evaluation_dataset_hash, evaluator_version
}
```

样本单位是预先定义且 horizon 完结的预测/经济机会，不是切片订单数。重叠持有期、同一行情事件和同源模型使样本相关；同时报告 raw N 与有效样本/分块置信区间。拒绝与未成交信号也保留独立评估，避免只看已执行获胜者；模拟标签与真实收益分列。

训练/校准/验证/最终测试按时间隔离，重叠标签做 purging/embargo。regime 特征只用当时可知标签，不用事后完美分类。按 regime/horizon 报告并对稀疏子组向总体收缩；多重尝试记录试验注册表，避免反复挑最优后冒充样本外。

Sharpe 明确采样频率、年化及自相关处理；最大回撤从完整权益路径计算；短样本不报看似精确的稳定年化。成本、换手、容量、极端情景与衰减共同评估。置信区间跨过无优势基线时，默认不提升权重。

权重更新流程：

1. 冻结数据截止与研究方案，达到政策规定的有效样本和覆盖要求。
2. 产出 MODEL_EVALUATED 与参数建议，附区间、退化场景、成本敏感性和旧版对照。
3. Governance 验证允许字段、权重和、单模型/簇上限、最大变动量与冷却期。
4. 在 SHADOW/PAPER 比较；通过才以未来生效时间发布参数版本，写 WEIGHT_UPDATED。
5. 性能退化或校准漂移触发降级/回滚到已批准版本；风险熔断仍锁存。

V2 默认只建议权重，不能自动激活。V3 即使允许有限自动更新，也只能在 Operator 授予的 Learned Parameters 范围内，不能修改能力、风险上限或数据准入规则。AI 提议新 Alpha 与自动上线是两件事。

## 12. Governance 模型

| 配置层 | 例子 | 修改主体与生效方式 |
|---|---|---|
| Immutable Safety Rules | 实盘写入禁用、学习无执行权限、账本不得覆写、模式隔离 | 运行期不可修改；只能通过显式审查的新软件/安全契约版本，不允许配置覆盖 |
| Operator Policy | 资产白名单、风险上限、TTL、授权模式、应急权限 | 有权限操作者，版本化审批与生效事件；须满足不可变规则 |
| Strategy Parameters | 特征窗口、进入/退出阈值、执行算法候选 | 研究提出，治理审批和样本外验证 |
| Learned Parameters | 校准器、有限权重、衰减估计 | 评估器提出，V2 治理激活；范围不能越层 |

配置优先级不是“最后写入获胜”。下层只能在上层允许集合内选择，冲突启动失败。所有政策记录 schema、内容哈希、变更理由、授权者、版本、生效时间、回滚目标；不允许回溯篡改历史决策所用政策。

角色拆分：Researcher 提案，Risk/Accounting 确定性服务核验，Operator 管理政策，ExecutionWorker 仅持短期受限能力，Auditor 只读。CZ Strategy / He Yi Growth 等 founder skills 位于研究建议层，只能提出问题和假说，不能成为交易指令或提高信号置信度的权威背书。

Kill 恢复需要外部状态核对、原因修复、政策权限验证和 RECOVERY_AUTHORIZED；重启进程不能清除 kill。V2 不存在 LIVE_EXECUTE，操作员也不能靠修改环境变量获得该能力。

## 13. Capability Matrix

以下是目标契约；允许不代表已实现。全局默认 DENY，未实现 Adapter 能力仍 DENY。所有联网读取也需来源和账户授权。

| Capability | RESEARCH | SHADOW | PAPER | TESTNET | LIVE_PROPOSAL |
|---|---|---|---|---|---|
| 历史/公共行情读取 | 是 | 是 | 是 | 是 | 是 |
| 实盘私人账户只读 | 否 | 可授权 | 否 | 否 | 可授权 |
| TestNet 私人账户读取 | 否 | 否 | 否 | 可授权 | 否 |
| Alpha/组合/Intent 计算 | 研究结果 | 旁路决策 | 模拟决策 | 测试决策 | 提案决策 |
| 模拟订单与模拟成交 | 离线回测，独立run | 否 | 是 | 否 | 否 |
| 构建订单 payload | 研究预览 | 旁路预览 | 模拟 | TestNet计划 | 实盘未签名提案 |
| TestNet spot LIMIT 提交 | 否 | 否 | 否 | 是，门控后 | 否 |
| TestNet 撤改写入 | 否 | 否 | 否 | 仅未来适配器认证后 | 否 |
| 实盘订单提交/撤改 | 否 | 否 | 否 | 否 | 否 |
| 提币/划转/借贷/保证金写入 | 否 | 否 | 否 | 否 | 否 |
| 生成 Live Manifest | 否 | 否 | 否 | 否 | 是，PROPOSAL_ONLY |
| 权重评估/建议 | 是 | 是 | 是 | 是 | 是 |
| 学习直接激活参数 | 否 | 否 | 否 | 否 | 否 |
| 重放时任何外部写入 | 否 | 否 | 否 | 否 | 否 |

SHADOW 不发单、不生成权威模拟 fills；若需要反事实模拟，创建独立 PAPER/RESEARCH run。LIVE_PROPOSAL 可读取经授权账户，核对外部已存在的真实仓位，但不声称是本系统自动执行。

CapabilityToken 绑定 subject、mode epoch、account、environment、具体操作集合、intent/plan hash、额度、expiry、policy version；网关和 dispatcher 独立验证。TestNet 只匹配已批准 host 与凭据域，不能通过修改 host 把 TestNet 能力转向实盘。

## 14. Invariants 与设计验收

### 14.1 永远不能违反的规则

1. Inferred 不能转换标签成为 Observed；派生链必须保留源证据类型。
2. 决策不读取 knowledge cutoff 之后才到达的数据；修订不能污染历史回测。
3. 缺失、过期、冲突、未知成交状态不能当作零或成功。
4. Alpha 不创建 Order，不修改风险预算，不拥有交易所写权限。
5. Risk 对每个子订单有效，批准不能跨对象、账户、模式或过期复用。
6. 任何新增承诺都必须通过全组合约束和原子预留；并发不得重复占用同一额度。
7. 未确认撤单、未知请求和部分成交保留真实/最坏风险占用。
8. Intent 表达目标敞口；重试不能再次买入整个目标。
9. 订单发送/接受/成交是三个独立事实；ACK 不产生仓位。
10. 每个 fill 幂等入账一次；迟到 fill 不因终态被丢弃。
11. Ledger 不可覆写；修正有补偿记录，无法解释的差额不吞掉。
12. 同一实际库存不能被多个虚拟仓位完整重复归属。
13. 重放没有外部副作用；历史 AI 输出作为输入记录而非重跑。
14. REAL、TESTNET、SIMULATED 的证据和账本不能互换。
15. 全部 V2 模式禁止实盘写单、撤改、提币、划转和借贷。
16. Learned Parameters 不能修改 Immutable Safety Rules / Operator Policy。
17. Kill 持久化且不因进程重启、充值、模式切换自动恢复。
18. 不可行执行计划不能通过放宽滑点、延长有效期或扩大数量强行完成。
19. 费用、数量、仓位和资金核算由确定性代码负责；模型文本不是账本。
20. 成本归因不双计；反事实收益与真实PnL分别展示。
21. 不把相关信号数量当独立样本数量；不把未校准分数当概率。
22. 所有模块对未知 schema、枚举、单位和能力默认拒绝，并保留可诊断原因。
23. canonical manifest hash 不等于授权签名；任何字段变化均要求新哈希和重新核验。
24. 原始证据保留范围不足时必须声明不可完整重放，不能仅凭日志存在声称可审计。

### 14.2 第一批实现必须通过的场景（本阶段仅规范）

| 场景 | 必须观察到的结果 |
|---|---|
| LLM 声称“明日确定解锁”无来源 | Inferred/缺证据，不能进入 Observed，不能获得已校准收益预测 |
| 最新价格但订单簿旧/序列断裂 | 对依赖深度的执行 BLOCK；其他合格研究仍可运行 |
| 同源三个趋势 Alpha 与一个反向 Alpha | 组权重上限、冲突记录，不按票数直接买入 |
| 宏观向好但流动性枯竭 | Regime 可共存，Risk 限制优先 |
| 两 worker 同时请求最后额度 | 最多一个完整预留成功，另一个缩减/拒绝 |
| 发送后超时、进程重启 | UNKNOWN，保留预留，查单对账，不重复发送 |
| 部分成交后信号失效 | 非零仓位继续计风险，撤余单/受限处置，不能直接 CLOSED |
| 撤单确认之前又成交 | 按 trade ID 入账并修正目标剩余量 |
| 把 TESTNET host 换成实盘 | 能力验证拒绝，不能产生签名实盘写请求 |
| 重放含 ORDER_SEND_REQUESTED 的历史 | 仅恢复投影，外部请求数为0 |
| 参数学习建议提高 daily loss limit | 越层拒绝，并记录违规建议 |
| 被 Risk 拒绝的币随后暴跌 | 只报告预注册反事实，真实PnL保持不变 |
| 来源修订宏观数据 | 旧决策仍引用旧 vintage，新决策引用新值 |
| 权益重估后预算超限 | available=0、breach可见，启动治理限定处置 |
| mode 切换时旧子单等待派发 | 旧 epoch 命令失效，已发送订单继续核对 |
| 同一 fill 重复/乱序到达 | 最终库存与费用不重复，投影与权威核对一致 |

## 15. V2 → V3 演进方向

### 15.1 本次交付与现有仓库映射

本次只增加设计文档。现有 README/SKILL、OpenClaw/Codex 安装、Gate只读、TestNet自动 LIMIT、Live Manifest及CI完整保留。不能把本文目标状态表述为已完成的系统重构。

| 现有组件 | 未来适配位置 | 兼容要求 |
|---|---|---|
| Crypto Signal Planner Skill | Research/Alpha evidence frontend | 旧调用方式继续工作，输出通过新契约验证 |
| validate_plan.py | Legacy plan translator + validation | 保留旧schema；新schema显式版本，不偷换字段意义 |
| position_size.py | Deterministic sizing primitive | 不冒充账户级 Risk Governor；单独复核精度和约束 |
| gate_client.py | Gate Adapter 的兼容入口 | 原live封锁、host guard、命令行不变 |
| auto_testnet_runner.py | 未来 TestNet composition root | 新路径先旁路验证，未完成门控不接管执行 |
| live_order_manifest.py | LIVE_PROPOSAL renderer | 旧指纹格式保留；新完整契约指纹另设版本字段 |
| founder-skills | 研究和治理讨论辅助 | 不进入数值核心或执行授权链 |
| GitHub Actions | 现有回归 + 将来的契约/重放门禁 | 不移除现有安全检查 |

### 15.2 分阶段门槛

| 阶段 | 交付 | 进入下一阶段的门槛 |
|---|---|---|
| V2.0 概念基线（本文） | 对象、边界、状态机、矩阵、invariants | 术语无冲突、关键失败场景有唯一处理语义 |
| V2.1 契约与黄金事件 | 小规模 schemas、固定样本、pure reducers | deterministic replay、版本迁移、去重和无副作用验证 |
| V2.2 风险与会计内核 | 预算预留、净值/库存账本、离线核对 | 并发预留、未知订单、部分成交、费用与更正一致性 |
| V2.3 旁路兼容 | 旧输出翻译、新旧比较、SHADOW/PAPER | 旧CLI/安装/CI全部通过，差异可解释 |
| V2.4 TestNet验证 | 门控后的单一 spot LIMIT 路径 | 故障注入、恢复和对账通过；不推断实盘盈利 |
| V3 受控研究扩展 | 多Alpha校准、组合优化、执行策略插件 | 每项独立样本外/成本/容量/适配器验收 |

V3 优先研究：条件依赖 ensemble、场景风险与尾部相关、cluster budget、保守 Kelly、可辨识归因、受限权重学习、多场所能力契约。新增交易所先做只读和提案，不因接口接通自动获得写权限。

真实资金自动执行**不在 V2 或上述默认 V3 路线授权内**。若未来单独讨论，须形成新的安全契约、权限架构和审查；不能靠新增枚举/环境变量绕过现有禁止规则。

### 15.3 仍需实证决定的事项

- 各资产/字段 TTL、source disagreement 阈值及 regime hysteresis 参数。
- Alpha 最小有效样本、校准方法、分组依赖估计、horizon 统一策略。
- 压力情景集、流动性退出假设、相关簇稳定性、风险 buffer。
- 交易成本/成交概率模型、虚拟仓位分配方法、反事实识别强度。
- 参数变更审批角色、离线证据保留期限和恢复服务目标。

这些需用可追溯数据和验收实验确定。本文选择抽象和默认拒绝行为，不捏造可盈利参数。

## 参考资料与证据边界

核对日期：2026-10-01。以上大部分条款是本项目设计决策，并非资料原文要求。没有回测、绩效或生产恢复验证结果。

1. [Microsoft — Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)：参考 append-only 事件、状态投影及快照模式。本文关于能力隔离、预算事务和重放无副作用是项目规范。
2. [Boyd et al. — Multi-Period Trading via Convex Optimization](https://arxiv.org/abs/1705.00109)：参考收益、风险、交易/持有成本及约束分离的优化框架，不提供本项目收益预测或盈利证据。
3. [Guo et al. — On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)：参考置信度校准问题；其分类实验不验证加密资产收益模型，本文要求额外样本外检验。
4. [Gate 官方 API v4 — Spot](https://www.gate.com/docs/developers/apiv4/en/spot/) 与 [官方 Python SDK Order schema](https://github.com/gateio/gateapi-python/blob/master/docs/Order.md)：用于识别场所订单字段和协议边界。自定义 text、查单与撤改行为须按实际适用地区/产品文档再次认证；本文不将自定义ID当作 exactly-once 保证。
5. 仓库基线 README、SKILL、references/gate-integration.md 及 scripts/gate_client.py、auto_testnet_runner.py、live_order_manifest.py：确认当前 live-readonly、TestNet spot LIMIT、未签名 proposal 及实盘写入封锁。没有读取私人账户或发送任何交易请求。
