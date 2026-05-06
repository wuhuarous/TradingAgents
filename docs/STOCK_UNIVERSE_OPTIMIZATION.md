# 股票池硬编码审计与优化说明

## 本次处理范围

已将会影响业务范围的股票池从代码中移出，统一通过 `tradingAgents.data.universe` 获取：

- 行情总览热门股票：`tradingAgents/server/routers/market.py`
- 智能选股候选范围：`tradingAgents/server/routers/screener.py`
- 模拟自动交易候选范围：`tradingAgents/trader/auto_strategy.py`
- 盘前观察名单：`tradingAgents/trader/scheduler/jobs.py`
- 日 K 同步名单：`tradingAgents/trader/scheduler/runner.py`
- A 股批量行情扫描：`tradingAgents/data/providers/a_stock.py`

股票配置集中到 `tradingAgents/config/stock_universe.json`，可按市场和角色维护：

- `hot`：行情总览展示
- `watchlist`：盘前分析观察
- `simulation`：模拟交易候选
- `screener`：智能选股候选
- `kline_sync`：日 K 同步

## 新机制

`tradingAgents/data/universe.py` 是统一入口：

- A 股：优先使用 AkShare 动态股票列表，并过滤 ST、退市风险名称；配置种子排在前面，保证流动性和质量基础。
- 港股/美股：当前项目内没有稳定免费的全市场列表，先使用可维护配置种子；后续接入 Polygon、Finnhub、Tushare Pro 或本地数据库后，只需要替换统一入口。
- 所有业务模块只调用 `get_universe()` 或 `get_universe_symbols()`，不再自己维护股票代码列表。

## 保留项

以下不属于业务股票池硬编码，暂时保留：

- 指数代码映射，例如上证指数、恒生指数、标普 500。这是市场基础设施代码，不参与个股选择范围。
- 单元测试中的 `AAPL` 等示例输入。
- 前端输入框 placeholder，例如 `600519 / AAPL / 0700.HK`，只是提示格式。
- 工具函数注释里的示例代码，例如 `600519 -> sh600519`。

## 后续建议

下一步可以把 `stock_universe.json` 升级为数据库表，例如 `stock_universe`：

- `market`
- `symbol`
- `name`
- `source`
- `is_active`
- `liquidity_rank`
- `quality_seed_score`
- `updated_at`

这样前端系统设置页可以直接管理股票宇宙，并记录每次 universe 变更对模拟收益和复盘结果的影响。
