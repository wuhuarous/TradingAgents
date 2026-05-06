# 优化文档

## 1. 优化总览

当前项目优化应围绕五条主线展开：

- 稳定性：数据、模型、配置、异常处理可控。
- 可解释性：每个结论都有证据、反证和失效条件。
- 可复盘性：每次运行都能保存、查询和比较。
- 可扩展性：数据源、模型、Agent、输出格式可替换。
- 可验证性：关键逻辑有测试，输出结构可校验。

## 2. 架构优化

### 2.1 分层建议

建议拆分为以下层次：

- Interface：CLI、API、未来 Web UI。
- Orchestration：Agent 图、流程控制、checkpoint。
- Agents：各类角色提示词和结构化输出。
- Services：数据服务、指标服务、新闻服务、记忆服务。
- Providers：LLM provider、data provider。
- Storage：cache、decision log、reports。
- Evaluation：回测、复盘、统计。

这样可以避免 Agent 直接依赖外部接口，使测试和替换更容易。

### 2.2 配置优化

建议建立统一配置对象，覆盖：

- LLM provider。
- quick/deep model。
- 数据源选择。
- 缓存目录。
- 报告输出目录。
- 最大 debate 轮数。
- risk profile。
- 是否启用 checkpoint。
- 是否启用 memory。

配置优先级：

1. CLI 参数。
2. 环境变量。
3. 配置文件。
4. 默认配置。

## 3. Agent 输出优化

### 3.1 强制结构化

所有 Agent 输出应先通过 schema 校验，再进入下一步。自然语言报告可以由结构化结果生成，不应成为系统内部唯一数据格式。

建议每个 Agent 输出：

- summary。
- signals。
- confidence。
- assumptions。
- risks。
- missing_data。
- recommendation。

### 3.2 降低幻觉风险

提示词中应明确：

- 不得编造财务数据。
- 数据缺失时必须写入 `missing_data`。
- 不确定时降低 confidence。
- 不允许把模型推测当作事实。
- 新闻和财报必须带来源或时间。

### 3.3 争议处理

多 Agent 系统的价值来自分歧，不是所有角色都同意。建议保留：

- bullish evidence。
- bearish evidence。
- unresolved conflicts。
- risk override reason。

当多空证据接近时，最终动作应倾向 `WATCH` 或 `HOLD`。

## 4. 数据层优化

### 4.1 DataProvider 接口

建议定义统一接口：

```python
class DataProvider:
    def get_price_history(self, ticker: str, start: str, end: str): ...
    def get_fundamentals(self, ticker: str): ...
    def get_news(self, ticker: str, start: str, end: str): ...
    def get_market_context(self, date: str): ...
```

### 4.2 缓存策略

建议按数据类型设置缓存：

- 日线行情：按 ticker/date 缓存。
- 财务数据：按 ticker/quarter 缓存。
- 新闻数据：按 ticker/date range 缓存。
- LLM 中间结果：按 prompt hash 缓存，仅用于开发调试。

缓存必须记录 source、fetched_at 和 ttl。

### 4.3 数据质量标记

每份数据进入 Agent 前应带质量信息：

- completeness。
- freshness。
- source。
- adjusted。
- known_gaps。

最终报告中应暴露关键数据缺口。

## 5. 风险控制优化

最终决策前必须执行风险检查：

- 最大仓位限制。
- 最大亏损限制。
- 波动率过滤。
- 财报/宏观事件过滤。
- 流动性过滤。
- 与市场指数相关性。
- 高不确定性降级为观望。

建议规则：

- `risk_level = extreme` 时禁止输出 `BUY` 或 `SELL`，除非用户显式选择高风险模式。
- `confidence < 0.55` 时输出 `WATCH` 或 `NO_ACTION`。
- 数据缺口严重时必须输出 warning。
- 没有止损条件时不输出明确交易建议。

## 6. 记忆与复盘优化

### 6.1 决策日志

建议每次运行保存：

- run_id。
- ticker。
- date。
- input config。
- agent summaries。
- final decision。
- generated_at。
- data sources。
- warnings。

### 6.2 复盘字段

后续可回填：

- actual_return_1d。
- actual_return_5d。
- actual_return_20d。
- benchmark_return。
- alpha。
- decision_quality。
- reflection。

### 6.3 记忆使用原则

记忆只应作为参考，不应覆盖最新数据。提示词应区分：

- 当前事实。
- 历史经验。
- 模型推断。

## 7. 测试优化

建议测试分层：

- Unit test：配置加载、schema 校验、risk rules。
- Integration test：一次 mock 数据的完整分析流程。
- Snapshot test：Markdown 报告结构。
- Contract test：DataProvider 和 LLMProvider 接口。
- Smoke test：CLI 能启动并处理一个示例 ticker。

优先补充以下测试：

- 缺少 API key 时提示清晰。
- 数据源失败时流程不中断。
- Agent 输出非法 JSON 时能重试或降级。
- 高风险输入不会生成强买入建议。
- 决策日志能成功写入。

## 8. 文档优化

README 建议补齐：

- 项目定位。
- 快速开始。
- 环境变量。
- CLI 示例。
- Python API 示例。
- 输出字段说明。
- 风险免责声明。
- 常见错误。

docs 建议保留：

- `PROJECT_ANALYSIS.md`
- `ITERATION_DOCUMENT.md`
- `OPTIMIZATION_DOCUMENT.md`
- `ARCHITECTURE.md`
- `DECISION_SCHEMA.md`
- `RUNBOOK.md`

## 9. 优先级排序

P0：

- 修复本地运行链路。
- 明确 `.env.example`。
- 统一最终输出 schema。
- 保存决策日志。
- 增加风险拦截。

P1：

- 抽象 provider。
- 增加缓存。
- 增加 checkpoint。
- 增加 smoke test。
- 补齐 README。

P2：

- 批量分析。
- 回测统计。
- Web UI。
- 多语言报告。
- 更多模型供应商。

## 10. 下一步行动

建议下一轮直接进入代码侧：

1. 修复当前 PowerShell/终端启动问题，恢复本地扫描能力。
2. 基于实际目录补充文件级分析。
3. 找到最终决策输出位置并加入 schema。
4. 找到 CLI 入口并统一参数校验。
5. 增加一次完整 smoke test。
6. 更新 README 的快速开始与风险说明。
