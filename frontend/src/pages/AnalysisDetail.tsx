import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import ResearchWorkflow from '../components/ResearchWorkflow';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

export default function AnalysisDetail() {
  const { symbol: routeSymbol } = useParams<{ symbol?: string }>();
  const [searchParams] = useSearchParams();
  const [symbol, setSymbol] = useState(routeSymbol || searchParams.get('symbol') || '');
  const [market, setMarket] = useState(searchParams.get('market') || 'a_stock');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [rankings, setRankings] = useState<any>(null);

  useEffect(() => {
    api.getSimulationRankings(8).then(setRankings).catch(() => {});
  }, []);

  const runAnalysis = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await api.runAnalysis(symbol.trim(), market);
      setResult(data);
    } catch (e: any) {
      setError(e.message || '分析失败');
    } finally {
      setLoading(false);
    }
  };

  const analysis = result?.analysis || {};
  const trade = result?.trader_decision || {};

  return (
    <div className="page">
      <header className="page-header">
        <h1>深度分析</h1>
        <p>10 智能体协作链路 · 市场分析 → 辩论 → 风险评估 → 交易决策</p>
      </header>

      <ResearchWorkflow active="analysis" />

      {/* Search bar */}
      <div className="analysis-searchbar" style={{
        display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)',
        alignItems: 'flex-end',
      }}>
        <div className="filter-group" style={{ flex: 1, maxWidth: 200 }}>
          <label className="filter-label">市场</label>
          <select
            className="filter-input"
            value={market}
            onChange={(e) => setMarket(e.target.value)}
          >
            {MARKETS.map((m) => (
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group" style={{ flex: 1 }}>
          <label className="filter-label">股票代码</label>
          <input
            type="text"
            className="filter-input"
            placeholder="例如 600519 / AAPL / 0700.HK"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
          />
        </div>
        <button
          className="btn-primary"
          onClick={runAnalysis}
          disabled={loading || !symbol.trim()}
          style={{ padding: 'var(--space-3) var(--space-6)' }}
        >
          {loading ? '分析中...' : '开始分析'}
        </button>
      </div>

      {rankings && (
        <section className="analysis-pick-strip">
          <div className="section-header">
            <h2>推荐深度分析对象</h2>
            <span className="section-badge">全市场候选</span>
          </div>
          <div className="market-leader-grid">
            {[...(rankings.quality_top10 || []).slice(0, 4), ...(rankings.potential_top10 || []).slice(0, 4)].map((item: any) => (
              <button
                className="leader-card"
                key={`${item.market}-${item.symbol}`}
                onClick={() => {
                  setSymbol(item.symbol);
                  setMarket(item.market);
                  setResult(null);
                }}
              >
                <div>
                  <strong>{item.symbol}</strong>
                  <p>{item.name}</p>
                </div>
                <span className={`action-pill ${String(item.action).toLowerCase()}`}>
                  {item.action === 'BUY' ? '买入' : item.action === 'WATCH' ? '观察' : item.action}
                </span>
                <b>{item.board_score ?? item.final_score}</b>
              </button>
            ))}
          </div>
        </section>
      )}

      {error && (
        <div className="empty-state" style={{ borderColor: 'var(--loss)', marginBottom: 'var(--space-6)' }}>
          <p style={{ color: 'var(--loss)' }}>{error}</p>
        </div>
      )}

      {loading && (
        <div style={{ padding: 'var(--space-16)', textAlign: 'center' }}>
          <div className="loading-spinner">
            <span className="loading-dot" />
            <span className="loading-dot" />
            <span className="loading-dot" />
          </div>
          <p style={{ color: 'var(--text-muted)', marginTop: 'var(--space-4)', fontSize: 'var(--font-size-sm)' }}>
            10 个 AI 智能体正在协作分析 {symbol}...
          </p>
        </div>
      )}

      {result && (
        <div className="analysis-pipeline">
          {/* Pipeline header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
            marginBottom: 'var(--space-8)',
          }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xl)', fontWeight: 700,
            }}>
              {result.symbol}
            </span>
            <Link to={`/stock?symbol=${encodeURIComponent(result.symbol)}&market=${market}`} style={{ color: 'var(--amber)', textDecoration: 'none' }}>
              查看行情详情
            </Link>
            {trade.action && (
              <span className={`stock-action ${trade.action}`}>
                {trade.action === 'buy' ? '买入信号' : trade.action === 'sell' ? '卖出信号' : '观望'}
              </span>
            )}
          </div>

          {/* Phase 1: Analysts */}
          <PipelinePhase title="第一阶段：并行分析" number={1}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-4)' }}>
              {analysis.market && (
                <AgentCard
                  agent="市场分析师"
                  score={analysis.market.score}
                  color="var(--amber)"
                >
                  <AgentKV label="趋势" value={analysis.market.trend} />
                  <AgentKV label="支撑位" value={analysis.market.support_level} />
                  <AgentKV label="阻力位" value={analysis.market.resistance_level} />
                  <AgentKV label="量能信号" value={analysis.market.volume_signal} />
                  {analysis.market.key_indicators && (
                    <AgentKV label="RSI" value={analysis.market.key_indicators.rsi} />
                  )}
                  {analysis.market.key_indicators?.macd_signal && (
                    <AgentKV label="MACD" value={analysis.market.key_indicators.macd_signal} />
                  )}
                  {analysis.market.reasoning && (
                    <AgentReasoning text={analysis.market.reasoning} />
                  )}
                </AgentCard>
              )}

              {analysis.fundamentals && (
                <AgentCard
                  agent="基本面分析师"
                  score={analysis.fundamentals.score}
                  color="var(--blue)"
                >
                  <AgentKV label="估值" value={analysis.fundamentals.valuation} />
                  <AgentKV label="增长前景" value={analysis.fundamentals.growth_outlook} />
                  {analysis.fundamentals.key_metrics && (
                    <>
                      <AgentKV label="PE" value={analysis.fundamentals.key_metrics.pe} />
                      <AgentKV label="PB" value={analysis.fundamentals.key_metrics.pb} />
                      <AgentKV label="ROE" value={analysis.fundamentals.key_metrics.roe} />
                      <AgentKV label="营收增长" value={analysis.fundamentals.key_metrics.revenue_growth} />
                    </>
                  )}
                  {analysis.fundamentals.risks?.length > 0 && (
                    <div style={{ marginTop: 'var(--space-3)' }}>
                      <div className="agent-label">风险因素</div>
                      <ul style={{ paddingLeft: 'var(--space-4)', fontSize: 'var(--font-size-sm)', color: 'var(--loss)' }}>
                        {analysis.fundamentals.risks.map((r: string, i: number) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {analysis.fundamentals.reasoning && (
                    <AgentReasoning text={analysis.fundamentals.reasoning} />
                  )}
                </AgentCard>
              )}

              {analysis.news && (
                <AgentCard
                  agent="新闻舆情分析师"
                  score={analysis.news.score}
                  color="var(--gain)"
                >
                  <AgentKV label="情绪" value={analysis.news.sentiment} />
                  {analysis.news.key_events?.length > 0 && (
                    <div style={{ marginTop: 'var(--space-3)' }}>
                      <div className="agent-label">关键事件</div>
                      {analysis.news.key_events.map((evt: any, i: number) => (
                        <div key={i} style={{
                          fontSize: 'var(--font-size-sm)', marginBottom: 'var(--space-2)',
                          padding: 'var(--space-2)', background: 'var(--bg-elevated)',
                          borderRadius: 'var(--radius-sm)',
                        }}>
                          <div style={{ fontWeight: 600 }}>{evt.event || evt.title}</div>
                          <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                            影响: {evt.impact || evt.importance || '—'}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {analysis.news.reasoning && (
                    <AgentReasoning text={analysis.news.reasoning} />
                  )}
                </AgentCard>
              )}
            </div>
          </PipelinePhase>

          {/* Phase 2: Bull vs Bear Debate */}
          <PipelinePhase title="第二阶段：多空辩论" number={2}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)' }}>
              {analysis.bull && (
                <div style={{
                  background: 'var(--bg-card)', border: '1px solid var(--gain-dim)',
                  borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
                }}>
                  <div className="agent-label" style={{ color: 'var(--gain)', fontSize: 'var(--font-size-md)', marginBottom: 'var(--space-4)' }}>
                    多头研究员
                  </div>
                  <div style={{ marginBottom: 'var(--space-3)' }}>
                    <span className="score-badge" style={{ background: 'var(--gain-dim)', color: 'var(--gain)' }}>
                      评分: {analysis.bull.overall_rating}/10
                    </span>
                  </div>
                  {analysis.bull.bull_points?.map((pt: any, i: number) => (
                    <div key={i} style={{
                      padding: 'var(--space-3) 0', borderBottom: '1px solid var(--border)',
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      fontSize: 'var(--font-size-sm)',
                    }}>
                      <span>{pt.point || pt.argument}</span>
                      <span style={{ color: 'var(--gain)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                        {(pt.confidence != null ? `${(pt.confidence * 100).toFixed(0)}%` : '')}
                      </span>
                    </div>
                  ))}
                  {analysis.bull.reasoning && (
                    <AgentReasoning text={analysis.bull.reasoning} />
                  )}
                </div>
              )}

              {analysis.bear && (
                <div style={{
                  background: 'var(--bg-card)', border: '1px solid var(--loss-dim)',
                  borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
                }}>
                  <div className="agent-label" style={{ color: 'var(--loss)', fontSize: 'var(--font-size-md)', marginBottom: 'var(--space-4)' }}>
                    空头研究员
                  </div>
                  <div style={{ marginBottom: 'var(--space-3)' }}>
                    <span className="score-badge" style={{ background: 'var(--loss-dim)', color: 'var(--loss)' }}>
                      评分: {analysis.bear.overall_rating}/10
                    </span>
                  </div>
                  {analysis.bear.bear_points?.map((pt: any, i: number) => (
                    <div key={i} style={{
                      padding: 'var(--space-3) 0', borderBottom: '1px solid var(--border)',
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      fontSize: 'var(--font-size-sm)',
                    }}>
                      <span>{pt.point || pt.argument}</span>
                      <span style={{ color: 'var(--loss)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                        {(pt.confidence != null ? `${(pt.confidence * 100).toFixed(0)}%` : '')}
                      </span>
                    </div>
                  ))}
                  {analysis.bear.reasoning && (
                    <AgentReasoning text={analysis.bear.reasoning} />
                  )}
                </div>
              )}
            </div>
          </PipelinePhase>

          {/* Phase 3: Research Manager Decision */}
          {analysis.research_decision && (
            <PipelinePhase title="第三阶段：研究结论" number={3}>
              <DecisionCard
                title="研究经理"
                decision={analysis.research_decision.decision}
                score={analysis.research_decision.final_score}
                confidence={analysis.research_decision.confidence}
                reasons={analysis.research_decision.key_reasons}
                riskSummary={analysis.research_decision.risk_summary}
                reasoning={analysis.research_decision.reasoning}
              />
            </PipelinePhase>
          )}

          {/* Phase 4: Risk Evaluations */}
          {analysis.risk_evaluations && (
            <PipelinePhase title="第四阶段：风险评估" number={4}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 'var(--space-4)' }}>
                {analysis.risk_evaluations.aggressive && (
                  <RiskCard label="激进派" data={analysis.risk_evaluations.aggressive} color="var(--loss)" />
                )}
                {analysis.risk_evaluations.neutral && (
                  <RiskCard label="中性派" data={analysis.risk_evaluations.neutral} color="var(--amber)" />
                )}
                {analysis.risk_evaluations.conservative && (
                  <RiskCard label="保守派" data={analysis.risk_evaluations.conservative} color="var(--gain)" />
                )}
              </div>
              {analysis.final_risk_params && (
                <div style={{
                  marginTop: 'var(--space-6)', padding: 'var(--space-5)',
                  background: 'var(--bg-elevated)', borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--amber)', borderLeft: '3px solid var(--amber)',
                }}>
                  <div className="agent-label" style={{ marginBottom: 'var(--space-3)' }}>最终风控参数（中性共识）</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-4)', fontSize: 'var(--font-size-sm)' }}>
                    <AgentKV label="仓位比例" value={analysis.final_risk_params.position_pct != null ? `${(analysis.final_risk_params.position_pct * 100).toFixed(0)}%` : '—'} />
                    <AgentKV label="止损线" value={analysis.final_risk_params.stop_loss_pct != null ? `${(analysis.final_risk_params.stop_loss_pct * 100).toFixed(1)}%` : '—'} />
                    <AgentKV label="止盈线" value={analysis.final_risk_params.take_profit_pct != null ? `${(analysis.final_risk_params.take_profit_pct * 100).toFixed(1)}%` : '—'} />
                  </div>
                </div>
              )}
            </PipelinePhase>
          )}

          {/* Phase 5: Trader Decision */}
          {Object.keys(trade).length > 0 && (
            <PipelinePhase title="第五阶段：交易决策" number={5}>
              <div style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-6)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-5)' }}>
                  <span className={`stock-action ${trade.action || 'hold'}`} style={{ fontSize: 'var(--font-size-lg)', padding: '4px 16px' }}>
                    {trade.action === 'buy' ? '买入' : trade.action === 'sell' ? '卖出' : '观望'}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--amber)' }}>
                    置信度: {trade.confidence != null ? `${(trade.confidence * 100).toFixed(0)}%` : '—'}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--space-4)', fontSize: 'var(--font-size-sm)' }}>
                  <AgentKV label="数量比例" value={trade.quantity_pct != null ? `${(trade.quantity_pct * 100).toFixed(0)}%` : '—'} />
                  <AgentKV label="买入下限" value={trade.price_lower != null ? `¥${trade.price_lower}` : '—'} />
                  <AgentKV label="买入上限" value={trade.price_upper != null ? `¥${trade.price_upper}` : '—'} />
                  <AgentKV label="止损价" value={trade.stop_loss != null ? `¥${trade.stop_loss}` : '—'} />
                  <AgentKV label="止盈价" value={trade.take_profit != null ? `¥${trade.take_profit}` : '—'} />
                  <AgentKV label="最大持有天数" value={trade.max_hold_days || '—'} />
                </div>
                {trade.reasoning && (
                  <AgentReasoning text={trade.reasoning} />
                )}
              </div>
            </PipelinePhase>
          )}
        </div>
      )}
    </div>
  );
}

/* ---- Sub-components ---- */

function PipelinePhase({ title, number, children }: { title: string; number: number; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 'var(--space-10)' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
        marginBottom: 'var(--space-5)',
      }}>
        <span style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--amber)', color: 'var(--text-inverse)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 'var(--font-size-xs)', fontWeight: 700,
        }}>
          {number}
        </span>
        <h2 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--font-size-lg)',
          fontWeight: 600,
        }}>
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

function AgentCard({ agent, score, color, children }: {
  agent: string; score: number; color: string; children: React.ReactNode;
}) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: `1px solid var(--border)`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 'var(--space-4)',
      }}>
        <div className="agent-label" style={{ fontSize: 'var(--font-size-md)' }}>{agent}</div>
        <span className="score-badge" style={{
          background: `${color}22`, color,
        }}>
          {score}/10
        </span>
      </div>
      {children}
    </div>
  );
}

function AgentKV({ label, value }: { label: string; value: any }) {
  const display = value != null ? String(value) : '—';
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border)',
      fontSize: 'var(--font-size-sm)',
    }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{display}</span>
    </div>
  );
}

function AgentReasoning({ text }: { text: string }) {
  if (!text) return null;
  return (
    <div style={{
      marginTop: 'var(--space-4)', padding: 'var(--space-3)',
      background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)',
      fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)',
      lineHeight: 1.6, fontStyle: 'italic',
    }}>
      {text}
    </div>
  );
}

function DecisionCard({ title, decision, score, confidence, reasons, riskSummary, reasoning }: {
  title: string; decision: string; score: number; confidence: number;
  reasons?: string[]; riskSummary?: string; reasoning?: string;
}) {
  const color = decision === 'buy' ? 'var(--gain)' : decision === 'sell' ? 'var(--loss)' : 'var(--amber)';
  return (
    <div style={{
      background: 'var(--bg-card)', border: `1px solid ${color}33`,
      borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 'var(--space-4)',
      }}>
        <div className="agent-label" style={{ fontSize: 'var(--font-size-md)' }}>{title}</div>
        <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
          <span className="score-badge" style={{ background: `${color}22`, color }}>
            评分: {score}/10
          </span>
          <span className="score-badge" style={{ background: 'var(--amber-dim)', color: 'var(--amber)' }}>
            置信度: {confidence != null ? `${(confidence * 100).toFixed(0)}%` : '—'}
          </span>
        </div>
      </div>

      <div style={{
        display: 'inline-block', padding: '4px 16px', borderRadius: '100px',
        fontSize: 'var(--font-size-lg)', fontWeight: 700,
        background: `${color}22`, color,
        marginBottom: 'var(--space-4)',
      }}>
        {decision === 'buy' ? '买入' : decision === 'sell' ? '卖出' : '观望'}
      </div>

      {reasons && reasons.length > 0 && (
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <div className="agent-label" style={{ marginBottom: 'var(--space-2)' }}>关键理由</div>
          <ul style={{ paddingLeft: 'var(--space-4)', fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
            {reasons!.map((r: string, i: number) => (
              <li key={i} style={{ marginBottom: 'var(--space-1)' }}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {riskSummary && (
        <div style={{
          padding: 'var(--space-3)', background: 'var(--loss-dim)',
          borderRadius: 'var(--radius-sm)', fontSize: 'var(--font-size-sm)',
          color: 'var(--loss)', marginBottom: 'var(--space-4)',
        }}>
          风险提示: {riskSummary}
        </div>
      )}

      {reasoning && <AgentReasoning text={reasoning} />}
    </div>
  );
}

function RiskCard({ label, data, color }: { label: string; data: any; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    }}>
      <div className="agent-label" style={{ color, fontSize: 'var(--font-size-md)', marginBottom: 'var(--space-4)' }}>
        {label}
      </div>
      <AgentKV label="仓位比例" value={data.position_pct != null ? `${(data.position_pct * 100).toFixed(0)}%` : '—'} />
      <AgentKV label="止损线" value={data.stop_loss_pct != null ? `${(data.stop_loss_pct * 100).toFixed(1)}%` : '—'} />
      <AgentKV label="止盈线" value={data.take_profit_pct != null ? `${(data.take_profit_pct * 100).toFixed(1)}%` : '—'} />
      {data.reasoning && <AgentReasoning text={data.reasoning} />}
    </div>
  );
}
