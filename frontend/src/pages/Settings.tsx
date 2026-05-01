import { useEffect, useState } from 'react';
import { api } from '../api/client';

const LLM_PROVIDERS = [
  { key: 'deepseek', label: 'DeepSeek', desc: '国产高性价比模型' },
  { key: 'openai', label: 'OpenAI', desc: 'GPT-4o 系列' },
  { key: 'anthropic', label: 'Anthropic', desc: 'Claude 系列' },
];

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Form state
  const [provider, setProvider] = useState('deepseek');
  const [deepseekKey, setDeepseekKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [deepThink, setDeepThink] = useState('deepseek-chat');
  const [quickThink, setQuickThink] = useState('deepseek-chat');
  const [capital, setCapital] = useState('1000000');
  const [posRatio, setPosRatio] = useState('0.2');
  const [totalRatio, setTotalRatio] = useState('0.8');
  const [stopLoss, setStopLoss] = useState('0.03');

  useEffect(() => {
    api.getSettings()
      .then((data) => {
        setSettings(data);
        const llm = data.llm || {};
        const trade = data.trading || {};
        setProvider(llm.provider || 'deepseek');
        setDeepseekKey(llm.deepseek_api_key || '');
        setOpenaiKey(llm.openai_api_key || '');
        setAnthropicKey(llm.anthropic_api_key || '');
        setDeepThink(llm.deep_think_model || 'deepseek-chat');
        setQuickThink(llm.quick_think_model || 'deepseek-chat');
        setCapital(String(trade.initial_capital ?? 1000000));
        setPosRatio(String(trade.single_position_max_ratio ?? 0.2));
        setTotalRatio(String(trade.total_position_max_ratio ?? 0.8));
        setStopLoss(String(trade.daily_stop_loss_ratio ?? 0.03));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.updateSettings({
        llm_provider: provider,
        deepseek_api_key: deepseekKey || undefined,
        openai_api_key: openaiKey || undefined,
        anthropic_api_key: anthropicKey || undefined,
        deep_think_model: deepThink,
        quick_think_model: quickThink,
        initial_capital: parseFloat(capital),
        single_position_max_ratio: parseFloat(posRatio),
        total_position_max_ratio: parseFloat(totalRatio),
        daily_stop_loss_ratio: parseFloat(stopLoss),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>系统配置</h1>
          <p>LLM 模型 · 风控参数 · 数据源</p>
        </header>
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>系统配置</h1>
        <p>LLM 模型选择 · 风控参数调整 · API 密钥管理</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-8)', maxWidth: 960 }}>
        {/* LLM Configuration */}
        <section>
          <div className="section-header" style={{ marginBottom: 'var(--space-6)' }}>
            <h2>LLM 大模型</h2>
          </div>

          <div className="settings-group">
            <label className="settings-label">提供商</label>
            <div className="provider-grid" style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)',
              marginBottom: 'var(--space-5)',
            }}>
              {LLM_PROVIDERS.map((p) => (
                <button
                  key={p.key}
                  className={`provider-card ${provider === p.key ? 'selected' : ''}`}
                  onClick={() => setProvider(p.key)}
                  style={{
                    padding: 'var(--space-3)',
                    border: provider === p.key ? '2px solid var(--amber)' : '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    background: provider === p.key ? 'var(--amber-dim)' : 'var(--bg-card)',
                    cursor: 'pointer',
                    textAlign: 'center',
                    transition: 'all var(--duration-fast) var(--ease-out)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-body)',
                    fontSize: 'var(--font-size-sm)',
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: 2 }}>{p.label}</div>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>{p.desc}</div>
                </button>
              ))}
            </div>

            <div className="filter-group" style={{ marginBottom: 'var(--space-4)' }}>
              <label className="settings-label">
                {provider === 'deepseek' ? 'DeepSeek API Key' :
                 provider === 'openai' ? 'OpenAI API Key' : 'Anthropic API Key'}
              </label>
              <input
                type="password"
                className="filter-input"
                placeholder="sk-..."
                value={
                  provider === 'deepseek' ? deepseekKey :
                  provider === 'openai' ? openaiKey : anthropicKey
                }
                onChange={(e) => {
                  if (provider === 'deepseek') setDeepseekKey(e.target.value);
                  else if (provider === 'openai') setOpenaiKey(e.target.value);
                  else setAnthropicKey(e.target.value);
                }}
              />
            </div>

            <div className="filter-group" style={{ marginBottom: 'var(--space-4)' }}>
              <label className="settings-label">深度思考模型</label>
              <input
                type="text"
                className="filter-input"
                value={deepThink}
                onChange={(e) => setDeepThink(e.target.value)}
              />
            </div>

            <div className="filter-group">
              <label className="settings-label">快速响应模型</label>
              <input
                type="text"
                className="filter-input"
                value={quickThink}
                onChange={(e) => setQuickThink(e.target.value)}
              />
            </div>
          </div>
        </section>

        {/* Risk Parameters */}
        <section>
          <div className="section-header" style={{ marginBottom: 'var(--space-6)' }}>
            <h2>风控参数</h2>
          </div>

          <div className="settings-group">
            <div className="filter-group" style={{ marginBottom: 'var(--space-4)' }}>
              <label className="settings-label">
                初始资金（¥{Number(capital).toLocaleString()}）
              </label>
              <input
                type="range"
                min="100000"
                max="10000000"
                step="100000"
                value={capital}
                onChange={(e) => setCapital(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>

            <div className="filter-group" style={{ marginBottom: 'var(--space-4)' }}>
              <label className="settings-label">
                单仓位上限（{(parseFloat(posRatio) * 100).toFixed(0)}%）
              </label>
              <input
                type="range"
                min="0.05"
                max="0.5"
                step="0.05"
                value={posRatio}
                onChange={(e) => setPosRatio(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>

            <div className="filter-group" style={{ marginBottom: 'var(--space-4)' }}>
              <label className="settings-label">
                总仓位上限（{(parseFloat(totalRatio) * 100).toFixed(0)}%）
              </label>
              <input
                type="range"
                min="0.3"
                max="1.0"
                step="0.05"
                value={totalRatio}
                onChange={(e) => setTotalRatio(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>

            <div className="filter-group">
              <label className="settings-label">
                日止损线（{(parseFloat(stopLoss) * 100).toFixed(1)}%）
              </label>
              <input
                type="range"
                min="0.01"
                max="0.1"
                step="0.005"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </section>
      </div>

      <div style={{ marginTop: 'var(--space-8)', display: 'flex', gap: 'var(--space-4)', alignItems: 'center' }}>
        <button className="btn-primary" onClick={handleSave} disabled={saving}
          style={{ padding: 'var(--space-3) var(--space-8)' }}>
          {saving ? '保存中...' : '保存配置'}
        </button>
        {saved && (
          <span style={{ color: 'var(--gain)', fontSize: 'var(--font-size-sm)' }}>
            配置已保存，重启服务后生效
          </span>
        )}
      </div>

      {/* Data Sources info card */}
      <section style={{ marginTop: 'var(--space-10)', maxWidth: 960 }}>
        <div className="section-header" style={{ marginBottom: 'var(--space-4)' }}>
          <h2>数据源</h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
          <div className="settings-card">
            <h3>A股行情</h3>
            <p>AkShare + BaoStock</p>
          </div>
          <div className="settings-card">
            <h3>港美股行情</h3>
            <p>yfinance</p>
          </div>
          <div className="settings-card">
            <h3>财经新闻</h3>
            <p>东方财富 + 全球快讯</p>
          </div>
          <div className="settings-card">
            <h3>Tushare</h3>
            <p>{settings?.data?.tushare_token ? '已配置' : '未配置'}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
