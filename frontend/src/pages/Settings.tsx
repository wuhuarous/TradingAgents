import { useEffect, useState } from 'react';
import { api } from '../api/client';

const LLM_PROVIDERS = [
  { key: 'deepseek', label: 'DeepSeek', desc: '国产高性价比模型' },
  { key: 'openai', label: 'OpenAI', desc: 'GPT-4o 系列' },
  { key: 'anthropic', label: 'Anthropic', desc: 'Claude 系列' },
];

const MODEL_PRESETS: Record<string, { deep: string[]; quick: string[]; defaultDeep: string; defaultQuick: string }> = {
  deepseek: {
    deep: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-reasoner', 'deepseek-chat'],
    quick: ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-chat', 'deepseek-reasoner'],
    defaultDeep: 'deepseek-v4-pro',
    defaultQuick: 'deepseek-v4-flash',
  },
  openai: {
    deep: ['gpt-4o', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4o-mini'],
    quick: ['gpt-4o-mini', 'gpt-4.1-mini', 'gpt-4o'],
    defaultDeep: 'gpt-4o',
    defaultQuick: 'gpt-4o-mini',
  },
  anthropic: {
    deep: ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
    quick: ['claude-3-5-haiku-latest', 'claude-3-5-sonnet-latest'],
    defaultDeep: 'claude-3-5-sonnet-latest',
    defaultQuick: 'claude-3-5-haiku-latest',
  },
};

const DATA_SOURCES = [
  { key: 'auto', label: '自动切换', desc: '当前生效：A股直连/缓存，港美股 yfinance' },
  { key: 'akshare', label: 'AkShare', desc: '部分生效：A股历史/财务 fallback' },
  { key: 'yfinance', label: 'yfinance', desc: '当前生效：港美股主链路' },
  { key: 'tushare', label: 'Tushare', desc: '已保存，行情路由待接入' },
];

const NEWS_SOURCES = [
  { key: 'auto', label: '自动聚合', desc: '国内 + 海外多源合并' },
  { key: 'alpha_vantage', label: 'Alpha Vantage', desc: '海外新闻和情绪' },
  { key: 'finnhub', label: 'Finnhub', desc: '海外市场新闻' },
  { key: 'polygon', label: 'Polygon', desc: '美股新闻' },
  { key: 'newsapi', label: 'NewsAPI', desc: '全球媒体搜索' },
  { key: 'tavily', label: 'Tavily', desc: '搜索型新闻补充' },
];

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  // Form state
  const [provider, setProvider] = useState('deepseek');
  const [deepseekKey, setDeepseekKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [deepThink, setDeepThink] = useState('deepseek-v4-pro');
  const [quickThink, setQuickThink] = useState('deepseek-v4-flash');
  const [capital, setCapital] = useState('1000000');
  const [posRatio, setPosRatio] = useState('0.2');
  const [totalRatio, setTotalRatio] = useState('0.8');
  const [stopLoss, setStopLoss] = useState('0.03');
  const [marketSource, setMarketSource] = useState('auto');
  const [newsSource, setNewsSource] = useState('auto');
  const [tushareToken, setTushareToken] = useState('');
  const [alphaVantageKey, setAlphaVantageKey] = useState('');
  const [finnhubKey, setFinnhubKey] = useState('');
  const [polygonKey, setPolygonKey] = useState('');
  const [newsapiKey, setNewsapiKey] = useState('');
  const [tavilyKey, setTavilyKey] = useState('');
  const modelPreset = MODEL_PRESETS[provider] || MODEL_PRESETS.deepseek;

  useEffect(() => {
    api.getSettings()
      .then((data) => {
        setSettings(data);
        const llm = data.llm || {};
        const trade = data.trading || {};
        const dataCfg = data.data || {};
        setProvider(llm.provider || 'deepseek');
        setDeepseekKey(llm.deepseek_api_key || '');
        setOpenaiKey(llm.openai_api_key || '');
        setAnthropicKey(llm.anthropic_api_key || '');
        setDeepThink(llm.deep_think_model || 'deepseek-v4-pro');
        setQuickThink(llm.quick_think_model || 'deepseek-v4-flash');
        setCapital(String(trade.initial_capital ?? 1000000));
        setPosRatio(String(trade.single_position_max_ratio ?? 0.2));
        setTotalRatio(String(trade.total_position_max_ratio ?? 0.8));
        setStopLoss(String(trade.daily_stop_loss_ratio ?? 0.03));
        setMarketSource(dataCfg.preferred_market_data_source || 'auto');
        setNewsSource(dataCfg.preferred_news_source || 'auto');
        setTushareToken(dataCfg.tushare_token || '');
        setAlphaVantageKey(dataCfg.alpha_vantage_api_key || '');
        setFinnhubKey(dataCfg.finnhub_api_key || '');
        setPolygonKey(dataCfg.polygon_api_key || '');
        setNewsapiKey(dataCfg.newsapi_api_key || '');
        setTavilyKey(dataCfg.tavily_api_key || '');
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setSaveMessage('');
    try {
      const payload: Record<string, any> = {
        llm_provider: provider,
        deep_think_model: deepThink,
        quick_think_model: quickThink,
        initial_capital: parseFloat(capital),
        single_position_max_ratio: parseFloat(posRatio),
        total_position_max_ratio: parseFloat(totalRatio),
        daily_stop_loss_ratio: parseFloat(stopLoss),
        preferred_market_data_source: marketSource,
        preferred_news_source: newsSource,
      };
      addSecret(payload, 'deepseek_api_key', deepseekKey);
      addSecret(payload, 'openai_api_key', openaiKey);
      addSecret(payload, 'anthropic_api_key', anthropicKey);
      addSecret(payload, 'tushare_token', tushareToken);
      addSecret(payload, 'alpha_vantage_api_key', alphaVantageKey);
      addSecret(payload, 'finnhub_api_key', finnhubKey);
      addSecret(payload, 'polygon_api_key', polygonKey);
      addSecret(payload, 'newsapi_api_key', newsapiKey);
      addSecret(payload, 'tavily_api_key', tavilyKey);
      const result = await api.updateSettings(payload);
      setSaved(true);
      setSaveMessage(result.message || '配置已保存，当前服务已生效');
      setTimeout(() => {
        setSaved(false);
        setSaveMessage('');
      }, 5000);
    } catch {
      setSaveMessage('保存失败，请检查输入和服务状态');
    } finally {
      setSaving(false);
    }
  };

  const handleProviderChange = (nextProvider: string) => {
    const preset = MODEL_PRESETS[nextProvider] || MODEL_PRESETS.deepseek;
    setProvider(nextProvider);
    setDeepThink(preset.defaultDeep);
    setQuickThink(preset.defaultQuick);
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-8)', maxWidth: 1180 }}>
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
                  onClick={() => handleProviderChange(p.key)}
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
              <select
                className="filter-input"
                value={deepThink}
                onChange={(e) => setDeepThink(e.target.value)}
              >
                {modelPreset.deep.map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label className="settings-label">快速响应模型</label>
              <select
                className="filter-input"
                value={quickThink}
                onChange={(e) => setQuickThink(e.target.value)}
              >
                {modelPreset.quick.map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Data Sources */}
        <section>
          <div className="section-header" style={{ marginBottom: 'var(--space-6)' }}>
            <h2>数据源</h2>
          </div>

          <div className="settings-group">
            <label className="settings-label">行情数据优先级</label>
            <div className="provider-grid settings-option-grid">
              {DATA_SOURCES.map((source) => (
                <button key={source.key} className={`provider-card ${marketSource === source.key ? 'selected' : ''}`} onClick={() => setMarketSource(source.key)}>
                  <div>{source.label}</div>
                  <span>{source.desc}</span>
                </button>
              ))}
            </div>

            <label className="settings-label" style={{ marginTop: 'var(--space-5)' }}>新闻资讯优先级</label>
            <div className="provider-grid settings-option-grid">
              {NEWS_SOURCES.map((source) => (
                <button key={source.key} className={`provider-card ${newsSource === source.key ? 'selected' : ''}`} onClick={() => setNewsSource(source.key)}>
                  <div>{source.label}</div>
                  <span>{source.desc}</span>
                </button>
              ))}
            </div>

            <div className="settings-key-grid">
              <SecretInput label="Tushare Token" value={tushareToken} onChange={setTushareToken} />
              <SecretInput label="Alpha Vantage Key" value={alphaVantageKey} onChange={setAlphaVantageKey} />
              <SecretInput label="Finnhub Key" value={finnhubKey} onChange={setFinnhubKey} />
              <SecretInput label="Polygon Key" value={polygonKey} onChange={setPolygonKey} />
              <SecretInput label="NewsAPI Key" value={newsapiKey} onChange={setNewsapiKey} />
              <SecretInput label="Tavily Key" value={tavilyKey} onChange={setTavilyKey} />
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
                初始资金（¥{formatCurrencyNumber(capital)}）
              </label>
              <div className="capital-input-row">
                <input
                  type="number"
                  className="filter-input"
                  min="10000"
                  step="10000"
                  value={capital}
                  onChange={(e) => setCapital(e.target.value)}
                />
                <span>用于空账户或下次清空后重新模拟</span>
              </div>
              <div className="capital-presets">
                {[100000, 500000, 1000000, 3000000, 5000000].map((value) => (
                  <button key={value} type="button" onClick={() => setCapital(String(value))}>
                    {formatShortMoney(value)}
                  </button>
                ))}
              </div>
              <input
                type="range"
                min="10000"
                max="10000000"
                step="10000"
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
            {saveMessage || '配置已保存，当前服务已生效'}
          </span>
        )}
        {!saved && saveMessage && (
          <span style={{ color: 'var(--loss)', fontSize: 'var(--font-size-sm)' }}>{saveMessage}</span>
        )}
      </div>

      <section className="settings-hint">
        <h2>配置建议</h2>
        <p>DeepSeek 已加入 v4 系列：深度任务建议 deepseek-v4-pro，快速任务建议 deepseek-v4-flash。余额不足时，深度分析会自动切换本地规则兜底。新闻源切换已接入后端并会影响海外资讯聚合；行情源当前只有 A股直连链路和港美股 yfinance 主链路，Tushare 等专业源会先保存配置，下一步接入到行情 Provider。</p>
      </section>
    </div>
  );
}

function SecretInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="filter-group">
      <label className="settings-label">{label}</label>
      <input type="password" className="filter-input" placeholder="未配置" value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function addSecret(payload: Record<string, any>, key: string, value: string) {
  if (value && !value.includes('*')) {
    payload[key] = value;
  }
}

function formatCurrencyNumber(value: string) {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return '0';
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
}

function formatShortMoney(value: number) {
  if (value >= 10000) {
    return `${value / 10000}万`;
  }
  return String(value);
}
