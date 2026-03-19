import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SnapshotHistoryRow } from "../types";

type PriceChartProps = {
  history: SnapshotHistoryRow[];
};

function chartData(history: SnapshotHistoryRow[]) {
  return history
    .filter((row) => row.last_trade_price !== null)
    .map((row) => ({
      observedAt: new Date(row.observed_at).toLocaleTimeString(),
      probability: row.last_trade_price,
    }));
}

export function PriceChart({ history }: PriceChartProps) {
  const data = chartData(history);

  if (data.length === 0) {
    return <div className="chart-empty">No history yet for this market.</div>;
  }

  return (
    <div className="chart-shell">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#d8dde8" />
          <XAxis dataKey="observedAt" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="probability"
            stroke="#1565c0"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
