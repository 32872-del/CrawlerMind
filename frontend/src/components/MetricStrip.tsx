import { Card, Statistic } from 'antd';

interface Metric {
  label: string;
  value: string | number;
  suffix?: string;
}

export function MetricStrip({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="metric-grid">
      {metrics.map((metric) => (
        <div key={metric.label}>
          <Card size="small" className="metric-card">
            <Statistic title={metric.label} value={metric.value} suffix={metric.suffix} />
          </Card>
        </div>
      ))}
    </div>
  );
}
