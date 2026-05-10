import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Cell,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';

interface PnLPoint {
  time: string;
  value: number;
  total_pnl?: number;
  total_value?: number;
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

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
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
            yAxisId="daily"
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
          <YAxis
            yAxisId="cumulative"
            orientation="right"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#d98b3a', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickFormatter={(v: number) => {
              if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(1)}万`;
              if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`;
              return v.toString();
            }}
            dx={4}
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
            formatter={(v: number, name: string, item: any) => {
              const fmt = (n: number) => `¥${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
              if (name === 'value') return [fmt(v), '当日盈亏'];
              if (name === 'total_pnl') return [fmt(v), '累计盈亏'];
              return [v, name];
            }}
            labelFormatter={(label: string, items: any[]) => {
              const point = items?.[0]?.payload;
              const total = Number(point?.total_pnl || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
              return `${label} · 累计盈亏 ¥${total}`;
            }}
          />
          <ReferenceLine y={0} stroke="#293040" yAxisId="daily" />
          <Bar yAxisId="daily" dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={28}>
            {data.map((point, index) => (
              <Cell key={`${point.time}-${index}`} fill={point.value >= 0 ? '#d9454b' : '#2ea87a'} />
            ))}
          </Bar>
          <Line
            yAxisId="cumulative"
            type="monotone"
            dataKey="total_pnl"
            stroke="#d98b3a"
            strokeWidth={2}
            dot={false}
            name="total_pnl"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
