# 参考项目借鉴清单

## 1. daily_stock_analysis

路径：`D:\project\daily_stock_analysis`

可借鉴点：

- 多数据源 fallback：`data_provider/base.py`、`realtime_types.py` 中有统一行情类型、熔断器、失败冷却和多源切换。
- 海外行情补充：README 中明确使用 Longbridge 作为港美股首选数据源，YFinance/AkShare 作为 fallback。
- 搜索增强资讯：`src/search_service.py` 支持 Tavily、SerpAPI、Brave、SearXNG 等搜索源，并有多 Key 轮询、错误计数、时间窗口过滤。
- 复盘/回测：测试集中有 backtest、analysis_history、analysis_metadata，适合借鉴为模拟交易后的收益回填和策略评分。

为什么借鉴：

- 当前项目行情总览和海外资讯容易受单一数据源影响，需要熔断和 fallback。
- 当前新闻只是列表聚合，缺少“最新消息、风险排查、业绩预期、行业分析”等维度化搜索。

建议落地：

- 增加统一 Quote 类型中的 `source` 字段。
- 给行情源增加 CircuitBreaker。
- 增加搜索型资讯服务，作为新闻源失败时的兜底。

## 2. qlib

路径：`D:\project\qlib`

可借鉴点：

- Recorder/Experiment：`qlib.workflow` 中把每次实验的参数、指标、报告分开记录。
- 回测评价指标：文档中覆盖 annualized_return、information_ratio、max_drawdown 等指标。
- 样本内/验证集/样本外：Qlib 标准 workflow 支持 train、valid、test 分段，适合判断策略是否过拟合。
- 专业组合回测：`SimulatorExecutor`、`TopkDropoutStrategy`、`PortAnaRecord` 可直接承担组合交易模拟和绩效分析。
- 真实交易约束：Qlib backtest 配置支持 `limit_threshold`、`open_cost`、`close_cost`、`min_cost`、`deal_price` 等约束。
- 因子框架：Alpha158、Alpha360 和自定义 DataHandler 可作为本项目因子工程的底座。
- Online workflow：`docs/hidden/online.rst` 里有 generate、execute、update 的在线模拟流程。
- 数据处理流水线：Data Handler 思路适合做标准化特征表。

为什么借鉴：

- 你的目标是模拟交易不断训练复盘，qlib 的实验记录和回测评价方式正好对应。
- 年化 50% 不能只看收益，还要看最大回撤、信息比率、胜率、盈亏比。
- 参数优化和样本外验证是判断策略有没有真实价值的核心，不能只用一次历史收益证明策略有效。
- 本项目更适合做数据整合、前端体验和 AI 解释，专业研究引擎应尽量复用 Qlib。

建议落地：

- 为每次模拟训练增加 `strategy_version`、`params`、`metrics`。
- 增加 1D/5D/20D 收益回填。
- 增加收益回撤比和信息比率。
- 新增 Qlib Adapter，把本项目因子评分、新闻情绪、龙虎榜资金事件转成 Qlib 信号。
- 新增三段式实验配置：训练区间、验证区间、样本外测试区间。
- 新增参数试验表和策略排行榜，记录每组参数的收益、回撤、夏普、胜率、样本外表现。
- 回测默认启用涨跌停、停牌、成交量、滑点、手续费和最低佣金约束，避免结果偏乐观。

## 3. TradingAgents-CN

路径：`D:\project\TradingAgents-CN`

可借鉴点：

- 增强新闻过滤：`tradingagents/utils/enhanced_news_filter.py` 有规则、语义相似度、本地分类模型的多层过滤。
- Alpha Vantage 新闻：`tradingagents/dataflows/providers/us/alpha_vantage_news.py` 接入海外新闻与情绪。
- WebSocket/SSE 进度：`app/worker.py`、`app/services/websocket_manager.py`、`web/components/async_progress_display.py` 适合借鉴深度分析进度展示。
- 配置系统：`docs/configuration` 和 `tradingagents/config` 中有统一配置、模型能力、Key 优先级的设计。

为什么借鉴：

- 当前深度分析失败时直接报错，应该有任务进度、失败阶段和 fallback。
- 当前新闻可能相关性不高，需要按公司名、股票代码、财报、风险关键词过滤。

建议落地：

- 增加新闻相关性评分。
- 深度分析改成任务式执行，并通过 WebSocket/SSE 推送进度。
- 模型配置增加 provider、模型能力、余额/Key 状态检查。

## 4. 已在本轮落地

- 深度分析 LLM 余额不足时自动切换本地规则兜底。
- 国际新闻新增 Alpha Vantage、Finnhub、Polygon、NewsAPI 可选渠道。
- 行情总览新增 WebSocket 推送接口。
- 涨幅榜/跌幅榜在数据全为 0 时也有 fallback 展示。
- 系统设置页增强模型和数据源配置。
- 全局颜色调整为 A股习惯：上涨红色，下跌绿色。
