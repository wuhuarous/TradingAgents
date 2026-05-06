# 迭代文档

## 1. 迭代目标

本轮迭代目标是将项目从“多 Agent 原型”推进到“可执行、可解释、可复盘的交易分析工作流”。

核心交付：

- 明确项目当前问题与产品方向。
- 定义下一阶段功能边界。
- 建立结构化决策输出标准。
- 规划 Agent、数据、风险、记忆和工程化改造。
- 为后续代码迭代提供验收标准。

## 2. 用户预期拆解

用户预期通常不是“看到多个 Agent 在聊天”，而是：

- 输入目标：股票代码、分析日期、风险偏好、分析深度。
- 系统执行：自动获取数据，多角色分析，争议讨论，风险审查。
- 输出结果：给出买入、持有、卖出或观望建议。
- 解释依据：说明支持证据、反对证据和关键不确定性。
- 后续复盘：记录当时判断，并能在未来检查表现。

因此，本项目的迭代重点应从“Agent 数量”转向“决策质量、稳定性和可审计性”。

## 3. 建议版本规划

### v0.1 可用分析流

目标：完成最小可用闭环。

范围：

- CLI 或 API 输入 ticker、date、risk_profile。
- 至少包含技术面、新闻/情绪、基本面、风险评估四类分析。
- 最终输出统一决策对象。
- 生成 Markdown 报告。
- 保存本次运行日志和决策结果。

验收标准：

- 用户能在本地完成一次完整分析。
- 输出中包含明确 action 和 confidence。
- 出错时能说明是数据、模型、配置还是系统异常。

### v0.2 结构化与复盘

目标：让结果可比较、可回测。

范围：

- Agent 输出 JSON schema。
- 决策记录写入本地 `memory` 或 `logs`。
- 增加历史决策查询。
- 增加实际收益回填入口。
- 支持同 ticker 最近决策回顾。

验收标准：

- 每次决策可通过唯一 run_id 查询。
- 可以导出 JSON 和 Markdown 两种结果。
- 可以对同一 ticker 的历史建议做简单统计。

### v0.3 数据源与模型解耦

目标：提升扩展性。

范围：

- 抽象 DataProvider 接口。
- 抽象 LLMProvider 接口。
- 为每类数据增加缓存。
- 增加配置文件和环境变量模板。
- 支持至少一个免费数据源和一个可选付费数据源。

验收标准：

- 更换数据源不需要改 Agent 逻辑。
- 更换模型供应商不需要改业务流程。
- API key 缺失时提示清晰。

### v0.4 风险优先与组合视角

目标：从单次建议升级为交易研究辅助。

范围：

- 加入仓位建议规则。
- 加入最大风险敞口限制。
- 引入波动率、回撤、事件风险检查。
- 最终建议必须经过 Risk Manager。
- 对高不确定性场景输出 `WATCH` 或 `NO_ACTION`。

验收标准：

- 高风险标的不会只因技术面信号而直接给出强买入。
- 每个交易建议都有失效条件。
- 报告中风险部分优先级高于收益叙事。

## 4. 决策输出标准

建议所有最终输出统一为以下结构：

```json
{
  "run_id": "20260502-NVDA-001",
  "ticker": "NVDA",
  "analysis_date": "2026-05-02",
  "action": "BUY | HOLD | SELL | WATCH | NO_ACTION",
  "confidence": 0.0,
  "time_horizon": "intraday | swing | medium_term | long_term",
  "risk_level": "low | medium | high | extreme",
  "position_sizing": {
    "suggested_weight": 0.0,
    "max_loss_pct": 0.0,
    "stop_loss": null
  },
  "supporting_evidence": [],
  "opposing_evidence": [],
  "invalidating_conditions": [],
  "agent_summaries": {
    "technical": "",
    "fundamental": "",
    "sentiment": "",
    "news": "",
    "risk": ""
  },
  "final_rationale": "",
  "warnings": []
}
```

字段说明：

- `action`：避免只用 buy/sell，保留观望和不行动。
- `confidence`：使用 0 到 1 的数值，便于统计。
- `risk_level`：必须由风险模块给出。
- `invalidating_conditions`：说明什么情况发生后当前判断失效。
- `warnings`：记录数据缺口、模型不确定性、极端波动等问题。

## 5. Agent 角色建议

保留必要角色，避免过度拆分：

- Market Data Agent：负责行情、成交量、波动率和指标摘要。
- Technical Analyst：负责趋势、支撑阻力、指标背离。
- Fundamental Analyst：负责估值、财务质量、盈利预期。
- News & Sentiment Analyst：负责新闻事件和市场情绪。
- Bull Researcher：组织支持交易的证据。
- Bear Researcher：组织反对交易的证据。
- Trader：形成初步交易计划。
- Risk Manager：审查仓位、止损、事件风险和不确定性。
- Portfolio Manager：给出最终 action。

## 6. 运行流程建议

推荐流程：

1. 参数校验。
2. 数据获取与缓存。
3. 指标计算。
4. 分析师并行生成结构化摘要。
5. 多空研究员辩论。
6. Trader 形成交易计划。
7. Risk Manager 审查。
8. Portfolio Manager 输出最终结论。
9. 写入决策日志。
10. 导出 Markdown/JSON 报告。

## 7. 验收清单

本轮之后，项目应至少满足：

- README 能让新用户完成安装和一次运行。
- `.env.example` 覆盖必要 key。
- 分析输出有 JSON schema。
- 报告中有风险、证据和失效条件。
- 失败时能定位问题类别。
- 至少有一组 smoke test。
- docs 中有迭代路线和优化建议。

## 8. 后续代码落地建议

终端恢复后，优先检查以下文件或模块：

- `README.md`
- `pyproject.toml` 或 `requirements.txt`
- `main.py`
- `cli/`
- `tradingagents/default_config.py`
- `tradingagents/graph/`
- `tradingagents/agents/`
- `tradingagents/dataflows/`
- `tests/`

检查完成后，把本文中的设计项映射为具体 issue 或 commit。
