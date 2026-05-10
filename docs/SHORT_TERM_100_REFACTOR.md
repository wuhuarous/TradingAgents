# 短线 100 分模型重构建议

## 现状定位

- 短线 100 分模型原先实现于 `tradingAgents/trader/auto_strategy.py` 的 `_short_term_snapshot`。
- 模拟交易买入逻辑在 `QualityMomentumStrategy.run_cycle` / `arun_cycle` 中，候选股 `action == "BUY"` 后按仓位比例买入。
- 卖出逻辑同样在 `run_cycle` / `arun_cycle` 中，主要依据止损、止盈、综合分跌破、情绪转弱。
- 加仓逻辑在 `_should_add_position`、`_place_add_order`、`_aplace_add_order`，条件是短线评分 80+、盈利持仓、站稳关键位且未跌破止损线。
- 原回测策略是 `BaselineMomentumBacktester`，使用价格动量排序，和短线 100 分模型不一致。

## 核心问题

- 评分逻辑和模拟交易强耦合，无法被回测、参数实验、单元测试稳定复用。
- 回测验证的不是实际自动交易正在使用的短线模型，策略排行榜容易误导。
- 短线模型没有独立输入/输出契约，前端难以展示完整 `score`、`components`、`reasons`、`warnings`、`trade_plan`。

## 重构方向

1. 将短线评分模型拆到 `tradingAgents/trader/strategy/short_term_100.py`。
2. 新增 `ShortTerm100Strategy`，统一输出：
   - `score`
   - `components`
   - `reasons`
   - `warnings`
   - `trade_plan`
3. `auto_strategy.py` 继续保留模拟交易流程，但评分改为调用 `ShortTerm100Strategy`。
4. 新增 `ShortTerm100BacktestStrategy`，按历史日线逐日计算信号，下一交易日执行，避免未来数据。
5. 回测保留 A 股交易约束：T+1、涨跌停、手续费、滑点、成交量参与上限、停牌/无成交。
6. 回测指标补齐收益率、最大回撤、胜率、盈亏比、交易明细。

## 后续建议

- 短线买卖点如果要验证 10:40、14:00、早盘第一分钟，必须接入分钟级数据。
- 市值、龙虎榜、资金流、新闻舆情如果进入回测，必须使用历史时点数据，不能用当前最新值回填历史。
- 策略排行榜应优先比较样本外收益、最大回撤、交易次数、盈亏比和参数稳定性，而不是只看单次总收益。
