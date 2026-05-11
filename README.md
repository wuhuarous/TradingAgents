<div align="center">

# 🚀 TradingAgents Quant Lab

### AI 驱动的多市场量化研究与模拟交易平台

面向 **A 股 / 港股 / 美股**，集成行情分析、智能选股、新闻舆情、策略回测、模拟交易与 AI 投研复盘能力。

<br/>

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react" />
  <img src="https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql" />
  <img src="https://img.shields.io/badge/ClickHouse-Market_Data-FFCC01?style=for-the-badge&logo=clickhouse" />
</p>

<p>
  <img src="https://img.shields.io/badge/AI-LLM%20Analysis-purple?style=flat-square" />
  <img src="https://img.shields.io/badge/Market-A%20Share%20%7C%20HK%20%7C%20US-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/Trading-Simulation-success?style=flat-square" />
  <img src="https://img.shields.io/badge/Backtest-Supported-blueviolet?style=flat-square" />
</p>

<br/>

> 不是一个简单的行情看板，而是一个面向个人量化研究的  
> **AI 投研工作台 + 策略验证系统 + 模拟交易训练平台**

<br/>

</div>

---

## ✨ 项目亮点

<table>
<tr>
<td width="33%">

### 📈 全市场行情观察

支持 A 股、港股、美股行情接入，提供指数行情、涨跌幅榜、成交额榜、市场热度、热门行业和概念板块观察能力。

</td>
<td width="33%">

### 🧠 AI 智能投研分析

结合行情、财务、新闻、舆情和技术指标，使用 LLM 生成可解释的股票分析、风险提示和复盘总结。

</td>
<td width="33%">

### 🎯 多因子智能选股

从质量、成长、估值、动量、流动性、新闻情绪、风险因子等多个维度构建股票评分模型。

</td>
</tr>

<tr>
<td width="33%">

### 🤖 自动模拟交易

支持自动买入、自动卖出、止盈止损、持仓监控、订单记录和模拟账户资产统计。

</td>
<td width="33%">

### 🔍 策略回测复盘

支持收益率、年化收益、最大回撤、夏普比率、胜率、交易明细和权益曲线分析。

</td>
<td width="33%">

### 🧪 Qlib 研究集成

支持导出 Qlib 格式数据，用于更专业的多因子建模、回测、参数调优和样本外验证。

</td>
</tr>
</table>

---

## 🧭 项目定位

TradingAgents Quant Lab 希望解决的是一个完整的投研闭环问题：

```mermaid
flowchart LR
    A[行情数据] --> B[新闻舆情]
    B --> C[因子评分]
    C --> D[智能选股]
    D --> E[模拟交易]
    E --> F[回测复盘]
    F --> G[策略优化]
    G --> C
```

项目核心目标不是预测明天一定涨跌，而是让每一次交易都有数据依据、每一次亏损都能复盘、每一次策略调整都能验证。

---

## 🖥️ 系统预览

<table>
<tr>
<td width="50%">

### 📊 仪表盘

![仪表盘](docs/images/dashboard.png)

聚合账户资产、持仓收益、市场状态、模拟训练进展和关键风险提示。

</td>
<td width="50%">

### 🌍 行情总览

![行情总览](docs/images/market.png)

展示指数行情、涨跌幅榜、成交额榜、市场热度、热门行业和热门概念。

</td>
</tr>

<tr>
<td width="50%">

### 🎯 智能选股

![智能选股](docs/images/screener.png)

基于全市场候选池进行多因子评分，筛选具备交易价值的观察标的。

</td>
<td width="50%">

### 🤖 模拟训练

![模拟训练](docs/images/simulation.png)

根据策略规则自动执行模拟买卖，并记录完整交易过程。

</td>
</tr>

<tr>
<td width="50%">

### 📉 回测复盘

![回测复盘](docs/images/backtest.png)

通过收益率、最大回撤、夏普比率、胜率和权益曲线评估策略稳定性。

</td>
<td width="50%">

### 📰 新闻资讯

![新闻资讯](docs/images/news.png)

聚合多源财经新闻，并进行标准化处理、情绪识别和质量评分。

</td>
</tr>
</table>

---

## 🧩 核心功能

| 模块 | 功能 | 说明 |
| --- | --- | --- |
| 📊 仪表板 | 资产与市场总览 | 查看账户资产、收益、持仓、市场热度和系统状态 |
| 🌍 行情总览 | 市场快照 | 指数、涨跌榜、成交额榜、热门行业、热门概念 |
| 🎯 智能选股 | 多因子评分 | 质量、成长、估值、动量、情绪、流动性、风险评分 |
| 📰 新闻资讯 | 多源新闻聚合 | 东方财富、新浪财经、百度财经、海外资讯、Tavily |
| 🧠 深度分析 | AI 股票分析 | 融合行情、财务、技术面、新闻和 LLM 推理 |
| 🤖 模拟训练 | 自动模拟交易 | 自动买入、卖出、止盈、止损、仓位管理 |
| 📉 回测复盘 | 策略验证 | 收益率、年化收益、最大回撤、夏普比率、胜率 |
| 🧪 Qlib 集成 | 量化研究 | 导出 Qlib 数据，支持专业因子研究和样本外验证 |
| ⚙️ 系统配置 | 参数管理 | 管理数据源、模型 Key、交易参数和任务调度 |

---

## 🏗️ 技术架构

```mermaid
flowchart TB
    subgraph Frontend[前端层]
        A1[React]
        A2[TypeScript]
        A3[Vite]
        A4[Recharts]
    end

    subgraph Backend[服务层]
        B1[FastAPI]
        B2[SQLAlchemy Async]
        B3[APScheduler]
        B4[LLM Engine]
    end

    subgraph Data[数据层]
        C1[PostgreSQL]
        C2[ClickHouse]
        C3[Market Snapshot]
        C4[News Store]
    end

    subgraph Source[数据源]
        D1[AkShare]
        D2[东方财富]
        D3[新浪财经]
        D4[yfinance]
        D5[Tavily]
    end

    subgraph Research[研究层]
        E1[Factor Model]
        E2[Backtest Engine]
        E3[Qlib Export]
        E4[Simulation Trader]
    end

    Source --> Backend
    Frontend --> Backend
    Backend --> Data
    Backend --> Research
    Research --> Data
```

---

## 🧠 AI 投研流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Market as 行情数据
    participant News as 新闻舆情
    participant Factor as 因子评分
    participant LLM as LLM 分析
    participant Trader as 模拟交易
    participant Review as 回测复盘

    User->>Market: 获取市场行情
    Market->>Factor: 生成基础因子
    News->>Factor: 注入新闻情绪
    Factor->>LLM: 提供候选股票与上下文
    LLM->>Trader: 输出分析结论和交易建议
    Trader->>Review: 记录订单、持仓和收益
    Review->>User: 输出复盘报告
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/wuhuarous/TradingAgents.git
cd TradingAgents
```

### 2. 创建 Python 虚拟环境

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

macOS / Linux：

```bash
source .venv/bin/activate
```

### 3. 安装后端依赖

```bash
pip install -e ".[dev]"
```

### 4. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

根据实际情况填写：

```env
POSTGRESQL_URL=postgresql+asyncpg://user:password@host:5432/tradingagents
CLICKHOUSE_URL=http://host:8123

DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
TUSHARE_TOKEN=
```

### 5. 启动后端服务

```bash
python -m uvicorn tradingAgents.server.main:app --host 127.0.0.1 --port 8000
```

### 6. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

### 7. 访问系统

| 服务 | 地址 |
| --- | --- |
| 前端页面 | http://127.0.0.1:3000 |
| 后端 API | http://127.0.0.1:8000 |
| 健康检查 | http://127.0.0.1:8000/api/health |

---

## 📦 项目结构

```text
TradingAgents/
├── tradingAgents/
│   ├── config/          # 全局配置、运行时配置、股票池配置
│   ├── data/            # 行情、新闻、社媒、数据库、事件存储
│   ├── engine/          # LLM 分析、规则兜底、数据流适配
│   ├── research/        # Qlib 数据导出和实验工作流
│   ├── server/          # FastAPI 路由和 API 模型
│   └── trader/          # 模拟账户、交易规则、自动策略、回测和调度器
│
├── frontend/
│   └── src/pages/       # 仪表板、行情、选股、资讯、分析、回测、模拟训练
│
├── docs/                # 需求、迭代、优化和参考项目文档
├── tests/               # 后端单元测试和 API 测试
└── README.md
```

---

## 🔥 短线 100 分模型

项目内置短线评分模型，将主观交易经验拆解成可量化、可回测、可复盘的规则。

| 条件 | 分数 | 说明 |
| --- | ---: | --- |
| 30 天内有涨停 | 15 | 过滤长期无异动个股 |
| 30 天内有倍量 | 10 | 判断是否存在资金关注 |
| 市值 100 亿以内 | 10 | 偏向弹性更高的短线标的 |
| 涨停后未跌破涨停日最低价 | 15 | 判断强势结构是否仍然有效 |
| 横盘突破或突破前高 | 15 | 捕捉平台突破和趋势启动 |
| 大盘下跌时个股抗跌 | 15 | 识别弱市中的相对强势 |
| 回调缩量且有承接 | 10 | 避免追高，等待回踩确认 |
| 下午 2 点后仍站稳关键位 | 10 | 过滤尾盘走弱的假突破 |

### 执行规则

| 分数区间 | 策略动作 |
| --- | --- |
| 80 分以下 | 暂不参与，仅保留观察 |
| 80 - 89 分 | 进入观察池，等待确认信号 |
| 90 分以上 | 允许更积极的模拟仓位 |
| 跌破关键位 | 触发止损或卖出观察 |
| 放量突破 | 允许加仓或重新评估 |

---

## 🤖 模拟交易规则

系统会尽量模拟真实 A 股交易约束：

| 规则 | 说明 |
| --- | --- |
| T+1 | 当日买入的普通 A 股，当日不可卖出 |
| 涨跌停保护 | 涨停附近不追高买入，跌停附近不强制卖出 |
| 停牌保护 | 停牌、无价格、无成交量标的不参与交易 |
| 成交量约束 | 单笔成交受当日成交量参与比例限制 |
| 交易成本 | 模拟佣金、过户费、印花税等交易成本 |
| 风险控制 | 支持止盈、止损、评分恶化和异常波动处理 |

---

## 📊 回测指标

| 指标 | 说明 |
| --- | --- |
| 总收益率 | 策略整体收益表现 |
| 年化收益率 | 折算后的年度收益表现 |
| 最大回撤 | 衡量策略历史最大亏损幅度 |
| 夏普比率 | 衡量单位风险下的收益能力 |
| 胜率 | 盈利交易占总交易次数比例 |
| 盈亏比 | 平均盈利与平均亏损的比例 |
| 交易明细 | 每一笔买卖的时间、价格、数量和原因 |
| 权益曲线 | 策略净值变化趋势 |

---

## 🧪 与 Qlib 的分工

TradingAgents Quant Lab 和 Qlib 的定位不同：

| 系统 | 定位 |
| --- | --- |
| TradingAgents Quant Lab | 负责数据采集、新闻舆情、智能选股、AI 分析、模拟交易和前端工作台 |
| Qlib | 负责专业因子研究、模型训练、策略回测、样本外测试和绩效评估 |

本项目可以将日线数据导出为 Qlib 格式，用于进一步开展更专业的量化研究。

---

## 🛠️ 常用命令

### 后端测试

```bash
PYTHONPATH=. pytest -q
```

### 前端构建

```bash
cd frontend
npm run build
```

### 手动触发模拟交易

```bash
curl -X POST "http://127.0.0.1:8000/api/simulation/run?market=a_stock"
```

### 查看调度器状态

```bash
curl "http://127.0.0.1:8000/api/scheduler/status"
```

---

## 🗺️ Roadmap

### 已完成

- [x] 全市场股票池接入
- [x] 多源新闻资讯聚合
- [x] 智能选股因子评分
- [x] 自动模拟交易
- [x] A 股交易规则模拟
- [x] 回测复盘能力
- [x] Qlib 数据导出
- [x] 仪表盘资产统计
- [x] 新闻情绪评分和质量评分

### 进行中

- [ ] 更稳定的数据源降级机制
- [ ] 更准确的停牌和涨跌停状态识别
- [ ] 多策略对比和策略排行榜
- [ ] 历史新闻与历史财务数据回测样本建设
- [ ] 风险预算、行业暴露和仓位归因
- [ ] 策略版本管理
- [ ] 前端工作流串联：行情 → 选股 → 分析 → 回测 → 模拟 → 复盘

---

## ⚠️ 风险声明

本项目仅用于：

- 编程学习
- 量化研究
- 策略验证
- 模拟交易
- AI 投研流程探索

本项目不构成任何投资建议，也不承诺任何收益。  
股票、基金、期货、数字资产等金融产品均存在本金亏损风险。

任何真实交易决策均应由使用者自行判断，并自行承担风险。

---

## 🙏 致谢

本项目在架构设计和量化方法论上参考了以下优秀项目：

- [TradingAgents](https://github.com/TauricResearch/TradingAgents)  
  多智能体交易框架，为分析师、研究员、交易员、风控和组合经理等 Agent 分层设计提供了重要参考。

- [Qlib](https://github.com/microsoft/qlib)  
  微软开源 AI 量化研究平台，为因子研究、实验管理、回测引擎和专业绩效评估体系提供了参考。

---

## 📄 License

当前项目主要用于个人研究、学习和原型验证。

正式开源前建议补充明确的 License 文件，例如：

- MIT License
- Apache License 2.0
- GPL License

---

<div align="center">

### ⭐ 如果这个项目对你有帮助，欢迎 Star 支持

**TradingAgents Quant Lab**  
让 AI 投研、量化选股、模拟交易和复盘优化形成完整闭环。

</div>
