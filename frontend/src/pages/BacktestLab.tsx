import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import ResearchWorkflow from '../components/ResearchWorkflow';

type BacktestRun = {
  run_id: string;
  strategy: string;
  market: string;
  period: string;
  status: string;
  initial_cash: number;
  final_value: number;
  metrics: Record<string, number>;
  params: Record<string, any>;
  warnings: string[];
  trade_count: number;
  started_at: string;
  finished_at: string;
  trades?: BacktestTrade[];
  equity_curve?: EquityPoint[];
};

type BacktestTrade = {
  date: string;
  symbol: string;
  name: string;
  action: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  amount: number;
  fee: number;
  reason: string;
};

type EquityPoint = {
  date: string;
  cash: number;
  positions_value: number;
  total_value: number;
  daily_return: number;
  drawdown: number;
  positions: Record<string, number>;
};

type LeaderboardItem = {
  strategy: string;
  engine: string;
  experiment_id: string;
  trial_id: string;
  score: number;
  annual_return: number;
  max_drawdown: number;
  sharpe: number;
  win_rate: number;
  test_annual_return: number;
  test_max_drawdown: number;
  test_sharpe: number;
  data_coverage: number;
  params: Record<string, any>;
};

type QlibProjectDataStatus = {
  source?: {
    available: boolean;
    row_count: number;
    symbol_count: number;
    start_date: string;
    end_date: string;
    error?: string;
  };
  target?: {
    available: boolean;
    symbol_count: number;
    target_dir: string;
  };
  exports?: Array<{
    export_id: string;
    status: string;
    symbol_count: number;
    row_count: number;
    start_date: string;
    end_date: string;
    finished_at: string;
    message: string;
  }>;
};

const markets = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

export default function BacktestLab() {
  const [market, setMarket] = useState('a_stock');
  const [period, setPeriod] = useState('6mo');
  const [universeLimit, setUniverseLimit] = useState(200);
  const [topN, setTopN] = useState(3);
  const [rebalanceDays, setRebalanceDays] = useState(20);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selected, setSelected] = useState<BacktestRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [researchRunning, setResearchRunning] = useState(false);
  const [qlibRunning, setQlibRunning] = useState(false);
  const [preparingQlib, setPreparingQlib] = useState(false);
  const [syncingKlines, setSyncingKlines] = useState(false);
  const [exportingProjectData, setExportingProjectData] = useState(false);
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([]);
  const [qlibStatus, setQlibStatus] = useState<any>(null);
  const [projectDataStatus, setProjectDataStatus] = useState<QlibProjectDataStatus | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    loadRuns(market);
    loadResearch(market);
  }, [market]);

  async function loadRuns(nextMarket = market) {
    setLoading(true);
    setError('');
    try {
      const data = await api.getBacktestRuns(nextMarket, 20);
      const nextRuns = data.runs || [];
      setRuns(nextRuns);
      if (nextRuns.length) {
        await selectRun(nextRuns[0].run_id);
      } else {
        setSelected(null);
      }
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  async function selectRun(runId: string) {
    setError('');
    try {
      const detail = await api.getBacktestRun(runId);
      setSelected(detail);
    } catch (err: any) {
      setError(readError(err));
    }
  }

  async function runBacktest() {
    setRunning(true);
    setError('');
    try {
      const result = await api.runBacktest({
        market,
        period,
        universe_limit: universeLimit,
        top_n: Math.min(topN, universeLimit),
        rebalance_days: rebalanceDays,
      });
      setSelected(result);
      await loadRuns(market);
      await selectRun(result.run_id);
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setRunning(false);
    }
  }

  async function loadResearch(nextMarket = market) {
    try {
      const [status, projectData, board] = await Promise.all([
        api.getQlibStatus(),
        api.getQlibProjectDataStatus(nextMarket),
        api.getStrategyLeaderboard(nextMarket, 10),
      ]);
      setQlibStatus(status);
      setProjectDataStatus(projectData);
      setLeaderboard(board.items || []);
    } catch {
      setQlibStatus(null);
      setProjectDataStatus(null);
      setLeaderboard([]);
    }
  }

  async function runResearchGrid() {
    setResearchRunning(true);
    setError('');
    try {
      await api.runResearchGrid({
        market,
        period,
        universe_limit: universeLimit,
        top_n_options: `${Math.max(1, topN)},${Math.min(20, topN + 2)}`,
        rebalance_options: `${Math.max(5, rebalanceDays - 10)},${rebalanceDays}`,
      });
      await loadResearch(market);
      await loadRuns(market);
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setResearchRunning(false);
    }
  }

  async function prepareQlibData() {
    setPreparingQlib(true);
    setError('');
    try {
      const status = await api.prepareQlibData();
      setQlibStatus(status);
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setPreparingQlib(false);
    }
  }

  async function syncProjectKlines() {
    setSyncingKlines(true);
    setError('');
    try {
      await api.syncDailyKlines(market, Math.min(Math.max(universeLimit, 5), 50));
      await loadResearch(market);
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setSyncingKlines(false);
    }
  }

  async function exportProjectData() {
    setExportingProjectData(true);
    setError('');
    try {
      await api.exportQlibProjectData({
        market,
        limit: Math.min(Math.max(universeLimit, 5), 6000),
        min_rows: 30,
        overwrite: true,
      });
      await loadResearch(market);
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setExportingProjectData(false);
    }
  }

  async function runQlibExperiment() {
    setQlibRunning(true);
    setError('');
    try {
      await api.runQlibExperiment({ top_n: 50, n_drop: 5 });
      await loadResearch(market);
    } catch (err: any) {
      setError(readError(err));
    } finally {
      setQlibRunning(false);
    }
  }

  const chartData = useMemo(() => {
    return (selected?.equity_curve || []).map((point) => ({
      time: formatDate(point.date),
      total_value: point.total_value,
      drawdown_pct: point.drawdown * 100,
      cash: point.cash,
      positions_value: point.positions_value,
    }));
  }, [selected]);

  const trades = selected?.trades || [];
  const metrics = selected?.metrics || {};

  return (
    <div className="backtest-page">
      <header className="page-header backtest-header">
        <div>
          <h1>回测复盘</h1>
          <p>用历史行情验证策略，保留真实收益、回撤和交易明细。</p>
        </div>
        <div className="simulation-mode">NO LOOK-AHEAD</div>
      </header>

      <ResearchWorkflow active="backtest" />

      <section className="backtest-control">
        <div className="backtest-fields">
          <label>
            <span className="filter-label">市场</span>
            <select className="filter-input" value={market} onChange={(e) => setMarket(e.target.value)}>
              {markets.map((item) => (
                <option value={item.key} key={item.key}>{item.label}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="filter-label">周期</span>
            <select className="filter-input" value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="3mo">3个月</option>
              <option value="6mo">6个月</option>
              <option value="1y">1年</option>
            </select>
          </label>
          <label>
            <span className="filter-label">股票池数量</span>
            <input className="filter-input" type="number" min={5} max={6000} value={universeLimit} onChange={(e) => setUniverseLimit(Number(e.target.value))} />
          </label>
          <label>
            <span className="filter-label">持仓数量</span>
            <input className="filter-input" type="number" min={1} max={20} value={topN} onChange={(e) => setTopN(Number(e.target.value))} />
          </label>
          <label>
            <span className="filter-label">调仓间隔</span>
            <input className="filter-input" type="number" min={5} max={60} value={rebalanceDays} onChange={(e) => setRebalanceDays(Number(e.target.value))} />
          </label>
        </div>
        <button className="btn-primary backtest-run-btn" onClick={runBacktest} disabled={running}>
          {running ? '回测中...' : '运行回测'}
        </button>
        <button className="btn-secondary backtest-run-btn" onClick={runResearchGrid} disabled={researchRunning}>
          {researchRunning ? '实验中...' : '参数实验'}
        </button>
      </section>

      {error && <div className="alert-error">{error}</div>}

      <section className="backtest-research-strip">
        <div>
          <div className="agent-label">研究引擎</div>
          <strong>{qlibStatus?.available ? 'Qlib 专业回测可用' : '本地研究基线'}</strong>
          <p>{qlibStatus?.message || '正在检测研究引擎状态'} {qlibStatus?.data?.message ? `· ${qlibStatus.data.message}` : ''}</p>
          <div className="qlib-data-grid">
            <span className={projectDataStatus?.source?.available ? 'qlib-data-pill good' : 'qlib-data-pill warn'}>
              项目日线 {formatInt(projectDataStatus?.source?.symbol_count)} 只 / {formatInt(projectDataStatus?.source?.row_count)} 行
            </span>
            <span className={projectDataStatus?.target?.available ? 'qlib-data-pill good' : 'qlib-data-pill warn'}>
              Qlib项目数据 {projectDataStatus?.target?.available ? `${formatInt(projectDataStatus?.target?.symbol_count)} 只` : '未生成'}
            </span>
            {projectDataStatus?.exports?.[0] && (
              <span className="qlib-data-pill">
                最近导出 {formatDate(projectDataStatus.exports[0].finished_at)} · {formatInt(projectDataStatus.exports[0].row_count)} 行
              </span>
            )}
          </div>
        </div>
        <div className="research-actions">
          <div className="backtest-param-strip">
            <span>样本内 60%</span>
            <span>验证 20%</span>
            <span>样本外 20%</span>
            <span>含交易约束</span>
          </div>
          <div className="research-button-row">
            <button className="btn-secondary mini-research-btn" onClick={syncProjectKlines} disabled={syncingKlines || exportingProjectData || preparingQlib || qlibRunning}>
              {syncingKlines ? '同步中...' : '同步日线'}
            </button>
            <button className="btn-secondary mini-research-btn" onClick={exportProjectData} disabled={exportingProjectData || preparingQlib || qlibRunning}>
              {exportingProjectData ? '导出中...' : '导出项目数据'}
            </button>
            <button className="btn-secondary mini-research-btn" onClick={prepareQlibData} disabled={preparingQlib || qlibRunning}>
              {preparingQlib ? '准备中...' : '准备数据'}
            </button>
            <button className="btn-secondary mini-research-btn" onClick={runQlibExperiment} disabled={qlibRunning || preparingQlib}>
              {qlibRunning ? 'Qlib运行中...' : 'Qlib实验'}
            </button>
          </div>
        </div>
      </section>

      <section className="section leaderboard-section">
        <div className="section-header">
          <h2>策略排行榜</h2>
          <span className="section-badge">{leaderboard.length} 组</span>
        </div>
        {leaderboard.length === 0 ? (
          <div className="empty-state compact-empty">
            <p>暂无参数实验</p>
            <div className="empty-hint">点击“参数实验”后会按样本外表现生成排行榜</div>
          </div>
        ) : (
          <div className="backtest-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>策略</th>
                  <th>综合分</th>
                  <th>样本外年化</th>
                  <th>样本外回撤</th>
                  <th>样本外夏普</th>
                  <th>整体年化</th>
                  <th>参数</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((item) => (
                  <tr key={item.trial_id}>
                    <td>
                      <strong>{strategyLabel(item.strategy)}</strong>
                      <div className="muted-text">{item.engine}</div>
                    </td>
                    <td className="mono">{formatNum(item.score)}</td>
                    <td className={`mono ${metricClass(item.test_annual_return)}`}>{formatPct(item.test_annual_return)}</td>
                    <td className="mono loss">{formatPct(item.test_max_drawdown)}</td>
                    <td className={`mono ${metricClass(item.test_sharpe)}`}>{formatNum(item.test_sharpe)}</td>
                    <td className={`mono ${metricClass(item.annual_return)}`}>{formatPct(item.annual_return)}</td>
                    <td className="mono">Top {item.params?.top_n} / {item.params?.rebalance_days}日</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="backtest-grid">
        <aside className="backtest-runs-panel">
          <div className="section-header">
            <h2>历史回测</h2>
            <span className="section-badge">{loading ? '加载中' : `${runs.length} 条`}</span>
          </div>
          {runs.length === 0 ? (
            <div className="empty-state compact-empty">
              <p>暂无回测记录</p>
              <div className="empty-hint">运行一次回测后会保存到数据库</div>
            </div>
          ) : (
            <div className="backtest-run-list">
              {runs.map((run) => (
                <button
                  className={`backtest-run-row ${selected?.run_id === run.run_id ? 'active' : ''}`}
                  key={run.run_id}
                  onClick={() => selectRun(run.run_id)}
                >
                  <div>
                    <strong>{run.run_id.replace('bt', '#')}</strong>
                    <span>{marketLabel(run.market)} · {periodLabel(run.period)} · {run.trade_count} 笔</span>
                  </div>
                  <b className={metricClass(run.metrics?.total_return || 0)}>
                    {formatPct(run.metrics?.total_return)}
                  </b>
                </button>
              ))}
            </div>
          )}
        </aside>

        <main className="backtest-detail">
          {!selected ? (
            <div className="empty-state">
              <p>选择或运行一轮回测</p>
              <div className="empty-hint">这里会展示收益、回撤、净值曲线和交易明细</div>
            </div>
          ) : (
            <>
              <div className="metrics-row backtest-metrics">
                <Metric title="总收益" value={formatPct(metrics.total_return)} tone={metricClass(metrics.total_return)} sub={`最终资产 ${formatMoney(selected.final_value)}`} />
                <Metric title="年化收益" value={formatPct(metrics.annual_return)} tone={metricClass(metrics.annual_return)} sub="按交易日折算" />
                <Metric title="最大回撤" value={formatPct(metrics.max_drawdown)} tone="loss" sub="越接近 0 越好" />
                <Metric title="夏普比率" value={formatNum(metrics.sharpe)} tone={metricClass(metrics.sharpe)} sub={`胜率 ${formatPct(metrics.win_rate)}`} />
              </div>

              <section className="backtest-note">
                <div>
                  <div className="agent-label">策略说明</div>
                  <p>{selected.params?.note || '价格动量基线回测'}</p>
                </div>
                <div className="backtest-param-strip">
                  <span>池 {selected.params?.universe_limit}</span>
                  <span>持仓 {selected.params?.top_n}</span>
                  <span>{selected.params?.rebalance_days} 日调仓</span>
                  <span>费率 {(Number(selected.params?.fee_rate || 0) * 100).toFixed(2)}%</span>
                </div>
              </section>

              <section className="backtest-chart-grid">
                <div className="chart-container">
                  <div className="section-header compact">
                    <h2>净值曲线</h2>
                    <span className="section-badge">{chartData.length} 点</span>
                  </div>
                  <EquityChart data={chartData} />
                </div>
                <div className="chart-container">
                  <div className="section-header compact">
                    <h2>回撤曲线</h2>
                    <span className="section-badge">{formatPct(metrics.max_drawdown)}</span>
                  </div>
                  <DrawdownChart data={chartData} />
                </div>
              </section>

              {selected.warnings?.length > 0 && (
                <section className="backtest-warning-panel">
                  <div className="agent-label">数据提示</div>
                  {selected.warnings.slice(0, 6).map((warning) => (
                    <p key={warning}>{warning}</p>
                  ))}
                </section>
              )}

              <section className="section">
                <div className="section-header">
                  <h2>交易明细</h2>
                  <span className="section-badge">{trades.length} 笔</span>
                </div>
                <div className="backtest-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>日期</th>
                        <th>标的</th>
                        <th>动作</th>
                        <th>价格</th>
                        <th>数量</th>
                        <th>金额</th>
                        <th>原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.slice().reverse().slice(0, 80).map((trade, index) => (
                        <tr key={`${trade.date}-${trade.symbol}-${trade.action}-${index}`}>
                          <td className="mono">{formatDate(trade.date)}</td>
                          <td>
                            <strong className="mono">{trade.symbol}</strong>
                            <div className="muted-text">{trade.name}</div>
                          </td>
                          <td><span className={`badge ${trade.action.toLowerCase()}`}>{trade.action}</span></td>
                          <td className="mono">{formatNum(trade.price)}</td>
                          <td className="mono">{formatNum(trade.quantity)}</td>
                          <td className="mono">{formatMoney(trade.amount)}</td>
                          <td>{reasonLabel(trade.reason)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </main>
      </section>
    </div>
  );
}

function Metric({ title, value, sub, tone }: { title: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{title}</div>
      <div className={`metric-value ${tone || ''}`}>{value}</div>
      <div className="metric-sub">{sub}</div>
    </div>
  );
}

function EquityChart({ data }: { data: any[] }) {
  if (!data.length) return <div className="chart-empty"><span>暂无净值数据</span></div>;
  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="backtestEquity" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#d4a853" stopOpacity={0.22} />
            <stop offset="100%" stopColor="#d4a853" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1c2332" vertical={false} />
        <XAxis dataKey="time" tick={{ fill: '#404a5e', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1c2332' }} />
        <YAxis tick={{ fill: '#404a5e', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${(Number(v) / 10000).toFixed(0)}万`} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [formatMoney(v), '总资产']} />
        <Area type="monotone" dataKey="total_value" stroke="#d4a853" strokeWidth={1.6} fill="url(#backtestEquity)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function DrawdownChart({ data }: { data: any[] }) {
  if (!data.length) return <div className="chart-empty"><span>暂无回撤数据</span></div>;
  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1c2332" vertical={false} />
        <XAxis dataKey="time" tick={{ fill: '#404a5e', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1c2332' }} />
        <YAxis tick={{ fill: '#404a5e', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${Number(v).toFixed(1)}%`} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(2)}%`, '回撤']} />
        <Line type="monotone" dataKey="drawdown_pct" stroke="#2ea87a" strokeWidth={1.6} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const tooltipStyle = {
  background: '#111620',
  border: '1px solid #293040',
  borderRadius: 6,
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 12,
  color: '#e3e6ed',
  padding: '8px 12px',
};

function readError(err: any) {
  return err?.message || '请求失败';
}

function formatPct(value?: number) {
  const n = Number(value || 0) * 100;
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function formatMoney(value?: number) {
  return `¥${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatNum(value?: number) {
  const n = Number(value || 0);
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatInt(value?: number) {
  return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatDate(value?: string) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function metricClass(value?: number) {
  return Number(value || 0) >= 0 ? 'gain' : 'loss';
}

function marketLabel(value: string) {
  return markets.find((item) => item.key === value)?.label || value;
}

function periodLabel(value: string) {
  const map: Record<string, string> = { '3mo': '3个月', '6mo': '6个月', '1y': '1年' };
  return map[value] || value;
}

function reasonLabel(value: string) {
  const map: Record<string, string> = {
    momentum_rank_in: '动量入选',
    rebalance_out: '调仓换出',
    rebalance_trim: '仓位修正',
  };
  return map[value] || value;
}

function strategyLabel(value: string) {
  const map: Record<string, string> = {
    baseline_momentum: '动量基线',
  };
  return map[value] || value;
}
