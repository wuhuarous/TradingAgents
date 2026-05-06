import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import ResearchWorkflow from '../components/ResearchWorkflow';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

const SCORE_KEYS = [
  { key: 'quality', label: '质量' },
  { key: 'growth', label: '成长' },
  { key: 'valuation', label: '估值' },
  { key: 'momentum', label: '行情' },
  { key: 'sentiment', label: '情绪' },
  { key: 'short_term', label: '短线' },
  { key: 'risk', label: '风险' },
];

export default function SimulationLab() {
  const [market, setMarket] = useState('a_stock');
  const [summary, setSummary] = useState<any>(null);
  const [readiness, setReadiness] = useState<any>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [universeTotal, setUniverseTotal] = useState<number>(0);
  const [runs, setRuns] = useState<any[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [events, setEvents] = useState<Record<string, any[]>>({});
  const [eventStore, setEventStore] = useState<any>(null);
  const [selected, setSelected] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryData, readinessData, candidateData, runData, positionData, orderData, newsEvents, quoteEvents, trainingEvents, reviewEvents, storeStatus] = await Promise.all([
        api.getSimulationSummary(),
        api.getQuantReadiness(),
        api.getSimulationCandidates(market, 12),
        api.getSimulationRuns(12),
        api.getPositions(),
        api.getOrders(20),
        api.getSimulationEvents('news', 8),
        api.getSimulationEvents('market_quote', 8),
        api.getSimulationEvents('training_sample', 8),
        api.getSimulationEvents('review_backfill', 8),
        api.getEventStoreStatus(),
      ]);
      const list = candidateData.candidates || [];
      setSummary(summaryData);
      setReadiness(readinessData);
      setCandidates(list);
      setUniverseTotal(candidateData.universe_total || 0);
      setRuns(runData.runs || []);
      setPositions(positionData || []);
      setOrders(orderData || []);
      setEvents({
        news: newsEvents.events || [],
        market_quote: quoteEvents.events || [],
        training_sample: trainingEvents.events || [],
        review_backfill: reviewEvents.events || [],
      });
      setEventStore(storeStatus);
      setSelected((prev: any) => list.find((item: any) => item.symbol === prev?.symbol) || list[0] || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '模拟训练数据加载失败');
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [market]);

  const runCycle = async () => {
    setRunning(true);
    setError('');
    try {
      const result = await api.runSimulationCycle(market);
      setRuns((prev) => [result, ...prev].slice(0, 12));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '自动模拟交易失败');
    } finally {
      setRunning(false);
    }
  };

  const backfillReviews = async () => {
    setRunning(true);
    setError('');
    try {
      await api.backfillSimulationReviews(20, true);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '复盘回填失败');
    } finally {
      setRunning(false);
    }
  };

  const targetPct = (summary?.target_annual_return || 0.5) * 100;
  const currentPct = (summary?.current_return || 0) * 100;
  const progress = Math.max(0, Math.min(100, (currentPct / targetPct) * 100));
  const buyCount = candidates.filter((item) => item.action === 'BUY').length;
  const watchCount = candidates.filter((item) => item.action === 'WATCH').length;
  const avgScore = useMemo(() => {
    if (!candidates.length) return 0;
    return candidates.reduce((sum, item) => sum + (item.final_score || 0), 0) / candidates.length;
  }, [candidates]);

  return (
    <div className="page simulation-page">
      <header className="page-header simulation-header">
        <div>
          <h1>模拟训练</h1>
          <p>新闻情绪 · 营收成长 · 行情趋势 · 风险止损 · 复盘学习</p>
        </div>
        <div className="simulation-mode">SIMULATION MODE</div>
      </header>

      <ResearchWorkflow active="simulation" />

      <div className="market-tabs">
        {MARKETS.map((m) => (
          <button
            key={m.key}
            className={`market-tab ${market === m.key ? 'active' : ''}`}
            onClick={() => setMarket(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="metrics-row simulation-metrics">
        <div className="metric-card primary">
          <div className="metric-label">年化目标</div>
          <div className="metric-value">{targetPct.toFixed(0)}%</div>
          <div className="target-progress">
            <span style={{ width: `${progress}%` }} />
          </div>
          <div className="metric-sub">当前进度 {currentPct.toFixed(2)}%</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">全市场覆盖</div>
          <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
            {universeTotal ? universeTotal.toLocaleString() : '-'}
          </div>
          <div className="metric-sub">当前候选均分 {avgScore.toFixed(1)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">交易信号</div>
          <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
            {buyCount} / {watchCount}
          </div>
          <div className="metric-sub">买入 / 观察</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">风控参数</div>
          <div className="metric-value" style={{ fontSize: 'var(--font-size-xl)' }}>
            {(summary?.rules?.stop_loss_pct * 100 || 8).toFixed(0)}% / {(summary?.rules?.take_profit_pct * 100 || 22).toFixed(0)}%
          </div>
          <div className="metric-sub">止损 / 止盈</div>
        </div>
      </div>

      <section className="simulation-control">
        <div>
          <div className="agent-label">训练闭环</div>
          <h2>用每一轮模拟交易校准选股权重</h2>
          <p>
            系统会扫描候选池，按质量、成长、估值、行情、新闻情绪和风险打分；
            达到阈值才模拟买入，触发止损、止盈或情绪转弱时模拟卖出，并把本轮决策写入复盘日志。
          </p>
        </div>
        <button className="btn-primary run-cycle-btn" onClick={runCycle} disabled={running || loading}>
          {running ? '训练中...' : '运行一轮模拟交易'}
        </button>
      </section>

      <section className="simulation-account-strip">
        <div>
          <div className="agent-label">自动交易账户</div>
          <h2>持仓会按最新行情重估</h2>
          <p>运行一轮模拟交易后，买入、卖出、止损和止盈都会写入订单；当前持仓的浮动盈亏来自最新价格与买入成本的差值。</p>
        </div>
        <div className="account-mini-grid">
          <div>
            <span>当前持仓</span>
            <strong>{positions.length}</strong>
          </div>
          <div>
            <span>最近订单</span>
            <strong>{orders.length}</strong>
          </div>
          <div>
            <span>浮动盈亏</span>
            <strong className={positions.reduce((sum, item) => sum + Number(item.pnl || 0), 0) >= 0 ? 'gain' : 'loss'}>
              {formatMoney(positions.reduce((sum, item) => sum + Number(item.pnl || 0), 0))}
            </strong>
          </div>
        </div>
      </section>

      {readiness && (
        <section className="readiness-panel compact">
          <div className="readiness-head">
            <div>
              <div className="agent-label">交易前置条件</div>
              <h2>当前准备度 {readiness.overall_score} / 100</h2>
              <p>系统会优先补齐影响自动交易可靠性的短板。</p>
            </div>
            <div className={`readiness-score ${readiness.status}`}>
              <strong>{readiness.summary?.run_count || 0}</strong>
              <span>训练轮次</span>
            </div>
          </div>
          <div className="readiness-grid">
            {(readiness.checks || []).map((item: any) => (
              <div className={`readiness-item ${item.status}`} key={item.key}>
                <div className="readiness-item-head">
                  <strong>{item.label}</strong>
                  <span>{statusLabel(item.status)}</span>
                </div>
                <div className="readiness-bar">
                  <i style={{ width: `${item.score}%` }} />
                </div>
                {item.issues?.[0] && <p>{item.issues[0]}</p>}
              </div>
            ))}
          </div>
          {readiness.next_actions?.length > 0 && (
            <div className="next-action-strip">
              {readiness.next_actions.slice(0, 3).map((action: string) => (
                <span key={action}>{action}</span>
              ))}
            </div>
          )}
        </section>
      )}

      {error && <div className="alert-error">{error}</div>}

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : (
        <div className="simulation-grid">
          <section className="candidate-panel">
            <div className="section-header">
              <h2>优质股候选</h2>
              <span className="section-badge">{candidates.length} 个</span>
            </div>
            <div className="candidate-list">
              {candidates.map((item) => (
                <button
                  key={item.symbol}
                  className={`candidate-row ${selected?.symbol === item.symbol ? 'active' : ''}`}
                  onClick={() => setSelected(item)}
                >
                  <div>
                    <div className="candidate-symbol">{item.symbol}</div>
                    <div className="candidate-name">{item.name}</div>
                  </div>
                  <div className="candidate-score">
                    <span className={`action-pill ${item.action.toLowerCase()}`}>{actionLabel(item.action)}</span>
                    <strong>{item.final_score?.toFixed?.(1) || item.final_score}</strong>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="detail-panel">
            {!selected ? (
              <div className="empty-state">
                <p>暂无候选数据</p>
              </div>
            ) : (
              <>
                <div className="detail-head">
                  <div>
                    <div className="detail-symbol">{selected.symbol}</div>
                    <div className="detail-name">{selected.name}</div>
                  </div>
                  <div className="detail-price">
                    <strong>{selected.price?.toFixed?.(2) || selected.price}</strong>
                    <span className={selected.change_pct >= 0 ? 'gain' : 'loss'}>
                      {selected.change_pct >= 0 ? '+' : ''}{selected.change_pct?.toFixed?.(2) || selected.change_pct}%
                    </span>
                  </div>
                </div>

                <div className="score-breakdown">
                  {SCORE_KEYS.map((score) => {
                    const value = selected.scores?.[score.key] ?? 0;
                    const width = score.key === 'risk' ? Math.min(value, 100) : Math.max(value, 2);
                    return (
                      <div className="score-line" key={score.key}>
                        <span>{score.label}</span>
                        <div className="score-track">
                          <div
                            className={score.key === 'risk' ? 'score-fill risk' : 'score-fill'}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <b>{value.toFixed ? value.toFixed(0) : value}</b>
                      </div>
                    );
                  })}
                </div>

                <div className="trade-plan-grid">
                  <div>
                    <span>建议动作</span>
                    <strong className={`action-text ${selected.action.toLowerCase()}`}>{actionLabel(selected.action)}</strong>
                  </div>
                  <div>
                    <span>风险等级</span>
                    <strong>{riskLabel(selected.risk_level)}</strong>
                  </div>
                  <div>
                    <span>止损位</span>
                    <strong>{selected.trade_plan?.stop_loss?.toFixed?.(2) || '-'}</strong>
                  </div>
                  <div>
                    <span>止盈位</span>
                    <strong>{selected.trade_plan?.take_profit?.toFixed?.(2) || '-'}</strong>
                  </div>
                  <div>
                    <span>买入模式</span>
                    <strong>{entryModeLabel(selected.trade_plan?.entry_mode)}</strong>
                  </div>
                  <div>
                    <span>计划仓位</span>
                    <strong>{formatPct(selected.trade_plan?.position_ratio || 0)}</strong>
                  </div>
                </div>

                {selected.short_term?.components?.length > 0 && (
                  <div className="short-score-panel">
                    <div className="agent-label">短线 100 分模型</div>
                    <div className="short-score-head">
                      <strong>{Number(selected.short_term.score || 0).toFixed(0)}</strong>
                      <span>{shortTierLabel(selected.short_term.buy_tier)}</span>
                    </div>
                    <div className="short-score-list">
                      {selected.short_term.components.map((item: any) => (
                        <div className={`short-score-row ${item.passed ? 'passed' : ''}`} key={item.key}>
                          <span>{item.label}</span>
                          <b>{item.earned}/{item.points}</b>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="evidence-grid">
                  <div>
                    <div className="agent-label">买入依据</div>
                    <ul>
                      {(selected.reasons || []).slice(0, 5).map((reason: string) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="agent-label">风险提示</div>
                    {selected.warnings?.length ? (
                      <ul>
                        {selected.warnings.slice(0, 5).map((warning: string) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted-text">暂无重大风险提示</p>
                    )}
                  </div>
                </div>

                <div className="news-strip">
                  <div className="agent-label">新闻情绪样本</div>
                  {selected.sentiment?.items?.length ? selected.sentiment.items.map((news: any) => (
                    <div className="news-mini" key={`${news.title}-${news.source}`}>
                      <span className={news.score >= 0 ? 'gain' : 'loss'}>{news.score.toFixed(2)}</span>
                      <p>{news.title}</p>
                    </div>
                  )) : <p className="muted-text">暂无个股新闻样本</p>}
                </div>
              </>
            )}
          </section>

          <section className="review-panel">
            <div className="section-header">
              <h2>复盘记录</h2>
              <span className="section-badge">{runs.length} 轮</span>
            </div>
            {runs.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                <p>还没有训练记录</p>
                <div className="empty-hint">运行一轮模拟交易后会写入复盘日志</div>
              </div>
            ) : (
              <div className="run-list">
                {runs.map((run) => (
                  <div className="run-card" key={run.run_id}>
                    <div className="run-head">
                      <strong>{run.run_id}</strong>
                      <span>{run.market}</span>
                    </div>
                    <div className="run-stats">
                      <span>订单 {run.orders?.length || 0}</span>
                      <span>决策 {run.decisions?.length || 0}</span>
                      <span>收益 {((run.review?.current_return || 0) * 100).toFixed(2)}%</span>
                    </div>
                    {run.decisions?.slice(0, 3).map((decision: any) => (
                      <p key={`${run.run_id}-${decision.symbol}-${decision.action}`}>
                        {decision.action} {decision.symbol} {decision.score ? `(${decision.score})` : ''}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="review-panel">
            <div className="section-header">
              <h2>当前持仓</h2>
              <span className="section-badge">{positions.length} 个</span>
            </div>
            {positions.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                <p>暂无持仓</p>
                <div className="empty-hint">只有候选股达到买入阈值时才会模拟买入</div>
              </div>
            ) : (
              <div className="position-mini-list">
                {positions.map((pos) => (
                  <div className="position-mini-row" key={pos.symbol}>
                    <div>
                      <strong>{pos.symbol}</strong>
                      <span>
                        {pos.name} · {marketLabel(pos.market)} · 持仓 {formatNumber(pos.quantity)} / 可卖 {formatNumber(pos.available_quantity ?? pos.quantity)}
                      </span>
                    </div>
                    <div>
                      <b>{formatMoney(pos.market_value)}</b>
                      <span className={Number(pos.pnl || 0) >= 0 ? 'gain' : 'loss'}>
                        {formatMoney(pos.pnl)} / {formatPct(pos.pnl_pct)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="review-panel">
            <div className="section-header">
              <h2>最近订单</h2>
              <span className="section-badge">{orders.length} 笔</span>
            </div>
            {orders.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                <p>暂无订单</p>
                <div className="empty-hint">点击“运行一轮模拟交易”后，满足条件的买卖会出现在这里</div>
              </div>
            ) : (
              <div className="order-mini-list">
                {orders.slice().reverse().slice(0, 8).map((order) => (
                  <div className="order-mini-row" key={order.order_id}>
                    <span className={`badge ${order.action}`}>{order.action === 'buy' ? '买入' : '卖出'}</span>
                    <div>
                      <strong>{order.symbol}</strong>
                      <p>{order.reason || '自动交易'}</p>
                    </div>
                    <b>{formatMoney(order.cost)}</b>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="review-panel">
            <div className="section-header">
              <h2>数据闭环</h2>
              <div className="section-actions">
                {eventStore && (
                  <span className={`store-status ${eventStore.connected ? 'ready' : 'fallback'}`}>
                    {eventStore.connected ? 'PostgreSQL' : 'JSONL'}
                  </span>
                )}
                <button className="mini-action-btn" onClick={backfillReviews} disabled={running}>复盘回填</button>
              </div>
            </div>
            <div className="data-loop-grid">
              <EventColumn title="新闻/舆情事件" items={events.news || []} />
              <EventColumn title="行情快照" items={events.market_quote || []} />
              <EventColumn title="训练样本" items={events.training_sample || []} />
              <EventColumn title="收益回填样本" items={events.review_backfill || []} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function actionLabel(action: string) {
  const map: Record<string, string> = {
    BUY: '买入',
    WATCH: '观察',
    HOLD: '持有',
    AVOID: '回避',
    NO_ACTION: '不行动',
    SKIP: '跳过',
  };
  return map[action] || action;
}

function riskLabel(level: string) {
  const map: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
    extreme: '极高',
    unknown: '未知',
  };
  return map[level] || level;
}

function entryModeLabel(mode?: string) {
  const map: Record<string, string> = {
    pilot: '短线试仓',
    aggressive: '短线进攻',
    quality_momentum: '质量动量',
    none: '不买入',
  };
  return map[mode || 'none'] || mode || '不买入';
}

function shortTierLabel(tier?: string) {
  const map: Record<string, string> = {
    aggressive: '进攻池',
    pilot: '观察池',
    watch: '观察',
    none: '未入池',
  };
  return map[tier || 'none'] || tier || '未入池';
}

function marketLabel(market: string) {
  return market === 'a_stock' ? 'A股' : market === 'hk_stock' ? '港股' : market === 'us_stock' ? '美股' : market;
}

function formatMoney(value: number) {
  const n = Number(value || 0);
  return `${n >= 0 ? '+' : '-'}¥${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatPct(value: number) {
  const n = Number(value || 0) * 100;
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    ready: '可推进',
    partial: '需补强',
    blocked: '未就绪',
  };
  return map[status] || status;
}

function EventColumn({ title, items }: { title: string; items: any[] }) {
  return (
    <div className="event-column">
      <div className="agent-label">{title}</div>
      {items.length === 0 ? (
        <p className="muted-text">暂无事件</p>
      ) : items.slice(0, 6).map((item) => (
        <div className="event-row" key={item.event_id}>
          <strong>{item.symbol || item.market || item.kind}</strong>
          <span>{item.source || item.action || item.status}</span>
          <p>{eventText(item)}</p>
        </div>
      ))}
    </div>
  );
}

function eventText(item: any) {
  if (item.title) return item.title;
  if (item.final_score !== undefined) return `${item.action || '-'} 评分 ${item.final_score}`;
  if (item.price !== undefined) return `价格 ${Number(item.price || 0).toFixed(2)} 涨跌 ${((item.change_pct || 0) * 100).toFixed(2)}%`;
  return `${item.horizon || ''} 收益 ${((item.return_pct || 0) * 100).toFixed(2)}%`;
}
