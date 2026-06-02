import { useBotPerformance, useBotProfit } from "@workspace/api-client-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { cn, formatPct, formatUsdt, profitClass } from "@/lib/utils";

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div className="bg-card border border-card-border rounded-lg p-3 shadow-xl text-xs">
      <p className="font-semibold mb-1">{label}</p>
      <p className={profitClass(d.value)}>Profit: {formatUsdt(d.value)}</p>
      <p className="text-muted-foreground">Trades: {payload[0]?.payload?.count}</p>
    </div>
  );
}

export default function Performance() {
  const { data: perfData, isLoading } = useBotPerformance();
  const { data: profit } = useBotProfit();
  const pairs = (perfData as any[]) ?? [];

  const chartData = [...pairs]
    .sort((a, b) => b.profit - a.profit)
    .slice(0, 12)
    .map(p => ({ name: p.pair.replace("/USDT", ""), profit: p.profit, count: p.count, pct: p.profit_pct }));

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Performance</h1>
        <p className="text-sm text-muted-foreground">Per-pair profit/loss breakdown</p>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {[
          { label: "Total profit",   value: formatUsdt(profit?.profit_all_coin),    sub: formatPct(profit?.profit_all_percent) },
          { label: "Closed profit",  value: formatUsdt(profit?.profit_closed_coin), sub: formatPct(profit?.profit_closed_percent) },
          { label: "Best pair",      value: profit?.best_pair ?? "—",              sub: "top performer" },
          { label: "Worst pair",     value: profit?.worst_pair ?? "—",             sub: "needs attention" },
        ].map(({ label, value, sub }) => (
          <div key={label} className="bg-card border border-card-border rounded-lg p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{label}</p>
            <p className="text-base font-bold tabular-nums">{value}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      <div className="bg-card border border-card-border rounded-lg p-5 mb-4">
        <h2 className="text-sm font-semibold mb-4">Profit by Pair (USDT)</h2>
        {isLoading ? (
          <div className="h-48 bg-muted rounded animate-pulse" />
        ) : chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
            No performance data yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
              <XAxis
                dataKey="name"
                tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }}
                axisLine={{ stroke: "hsl(217 33% 17%)" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={55}
                tickFormatter={v => `${v > 0 ? "+" : ""}${v.toFixed(2)}`}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.profit >= 0 ? "hsl(160 84% 39%)" : "hsl(0 72% 51%)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Pair table */}
      <div className="bg-card border border-card-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/50">
              {["Pair", "Trades", "Profit (USDT)", "Profit (%)"].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td colSpan={4} className="px-4 py-3">
                    <div className="h-4 bg-muted rounded animate-pulse" />
                  </td>
                </tr>
              ))
            ) : pairs.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-muted-foreground text-sm">
                  No performance data yet — run some trades first.
                </td>
              </tr>
            ) : (
              [...pairs].sort((a, b) => b.profit - a.profit).map((p: any) => (
                <tr key={p.pair} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-semibold">{p.pair}</td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{p.count}</td>
                  <td className={cn("px-4 py-3 font-medium tabular-nums", profitClass(p.profit))}>
                    {formatUsdt(p.profit)}
                  </td>
                  <td className={cn("px-4 py-3 font-medium tabular-nums", profitClass(p.profit_pct))}>
                    {formatPct(p.profit_pct)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
