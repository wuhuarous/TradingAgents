import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

interface PnLPoint {
  time: string;
  value: number;
}

export default function PnLChart({ data }: { data: PnLPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="chart-container">
        <div className="chart-empty">
          <div className="chart-empty-icon">⎔</div>
          <span>暂无盈亏数据</span>
          <span style={{ fontSize: 12 }}>完成交易后将自动生成走势</span>
        </div>
      </div>
    );
  }

  const pnlKey = 'value';
  const gradientId = 'pnlGradient';

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d4a853" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#d4a853" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1c2332"
            vertical={false}
          />
          <XAxis
            dataKey="time"
            axisLine={{ stroke: '#1c2332' }}
            tickLine={false}
            tick={{ fill: '#404a5e', fontSize: 11, fontFamily: 'Inter' }}
            dy={8}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#404a5e', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickFormatter={(v: number) => {
              if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(1)}万`;
              if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`;
              return v.toString();
            }}
            dx={-4}
          />
          <Tooltip
            contentStyle={{
              background: '#111620',
              border: '1px solid #293040',
              borderRadius: 6,
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 12,
              color: '#e3e6ed',
              padding: '8px 12px',
            }}
            formatter={(v: number) => [
              `¥${v.toLocaleString()}`,
              '累计盈亏',
            ]}
          />
          <Area
            type="monotone"
            dataKey={pnlKey}
            stroke="#d4a853"
            strokeWidth={1.5}
            fill={`url(#${gradientId})`}
            dot={false}
            activeDot={{
              r: 4,
              fill: '#d4a853',
              stroke: '#0e111a',
              strokeWidth: 2,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
