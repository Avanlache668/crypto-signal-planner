# ADR-001: V2 安全边界与模块化单体

- 状态：Accepted
- 日期：2026-10-01

## 决策

V2 使用 Python 标准库模块化单体和 SQLite 事务存储。核心对象使用 `Decimal`、显式 UTC、版本字段和注入的时间/ID/数据源。交易所协议只存在于 adapter 边界。

真实资金订单、撤改、提币、划转、借贷和保证金写入是代码级 immutable deny，不接受环境变量、HTTP 开关或 Learned Parameters 覆盖。`LIVE_PROPOSAL` 只输出未签名提案；Gate TestNet 仅允许严格匹配官方 host 的门控现货 LIMIT。

## 理由

单机事务可先保证预算、事件、账本和 outbox 的可审计语义，避免在尚未验证正确性前引入分布式一致性。安全限制放在能力矩阵与 adapter 双重门控中，避免策略、AI 或学习层获得外部写权限。

## 影响

- 默认演示完全离线、无需凭据。
- SQLite 适合单进程/低并发控制面；多进程规模化前需独立验证事务与迁移。
- TestNet 发送仍沿用现有兼容入口，V2 CLI 不主动发送测试订单。
- 不支持的 TWAP、POV、ICEBERG 明确返回不支持，不做静默降级。

