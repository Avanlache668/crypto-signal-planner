# 故障恢复手册

1. 停止 dispatcher；不要删除数据库或释放 UNKNOWN 预留。
2. 运行 `python -m trading_os.cli --db trading-os.db status` 查看 kill、预算和订单。
3. 运行 `python -m trading_os.cli --db trading-os.db replay`；必须显示 `external_write_requests: 0`。
4. 对 UNKNOWN 请求使用场所只读查询核对订单、成交和余额。没有唯一证据时禁止重发。
5. 用补偿事件记录修正，不更新或删除历史事件。
6. kill 恢复要求原因已修复、外部状态已核对和有权限的恢复授权；重启或切模式不能解除。
7. 快照哈希失败时丢弃快照，从事件日志重建；事件哈希链失败时停止并保留证据。

备份至少包含 SQLite 主库、risk 库、配置版本和 fixture/原始证据哈希。秘密不得进入备份事件载荷。

