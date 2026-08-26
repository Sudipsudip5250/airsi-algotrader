import { useBotPerformance, useBotProfit } from "@workspace/api-client-react";
import type { PairPerformance } from "@workspace/api-client-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn, formatPct, formatUsdt, profitClass } from "@/lib/utils";
import { QueryError, QueryEmpty } from "@/components/QueryState";

type ChartDatum = { name: string; profit: number; count: number; pct: number };
type TooltipPayload = { value?: number; payload?: ChartDatum };

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayload[]; label?: string | number }) {
  if (!active || !payload?.length) return null;
  const value = payload[0]?.value;
  const count = payload[0]?.payload?.count;
  return <div className="rounded-lg border border-card-border bg-card p-3 text-xs shadow-xl"><p className="mb-1 font-semibold">{label}</p><p className={profitClass(value)}>Profit: {formatUsdt(value)}</p><p className="text-muted-foreground">Trades: {count ?? "—"}</p></div>;
}

export default function Performance() {
  const performanceQuery = useBotPerformance();
  const profitQuery = useBotProfit();
  const pairs = performanceQuery.data ?? [];
  const chartData: ChartDatum[] = [...pairs].sort((a, b) => b.profit - a.profit).slice(0, 12).map((pair) => ({ name: pair.pair.replace("/USDT", ""), profit: pair.profit, count: pair.count, pct: pair.profit_pct }));
  const sortedPairs = [...pairs].sort((a, b) => b.profit - a.profit);

  return <div className="mx-auto max-w-6xl p-6">
    <div className="mb-6"><h1 className="text-xl font-bold">Performance</h1><p className="text-sm text-muted-foreground">Per-pair profit/loss breakdown</p></div>
    {performanceQuery.isError || profitQuery.isError ? <div className="mb-4"><QueryError /></div> : null}
    <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">{[
      { label: "Total profit", value: formatUsdt(profitQuery.data?.profit_all_coin), sub: formatPct(profitQuery.data?.profit_all_percent) },
      { label: "Closed profit", value: formatUsdt(profitQuery.data?.profit_closed_coin), sub: formatPct(profitQuery.data?.profit_closed_percent) },
      { label: "Best pair", value: profitQuery.data?.best_pair ?? "—", sub: "top performer" },
      { label: "Worst pair", value: profitQuery.data?.worst_pair ?? "—", sub: "needs attention" },
    ].map(({ label, value, sub }) => <div key={label} className="rounded-lg border border-card-border bg-card p-4"><p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{label}</p><p className="text-base font-bold tabular-nums">{value}</p><p className="mt-0.5 text-xs text-muted-foreground">{sub}</p></div>)}</div>

    <div className="mb-4 rounded-lg border border-card-border bg-card p-5"><h2 className="mb-4 text-sm font-semibold">Profit by Pair (USDT)</h2>{performanceQuery.isLoading ? <div className="h-48 animate-pulse rounded bg-muted" /> : chartData.length === 0 ? <QueryEmpty message="No performance data yet" /> : <ResponsiveContainer width="100%" height={220}><BarChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}><XAxis dataKey="name" tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} axisLine={{ stroke: "hsl(217 33% 17%)" }} tickLine={false} /><YAxis tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} axisLine={false} tickLine={false} width={55} tickFormatter={(value: number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}`} /><Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} /><Bar dataKey="profit" radius={[4, 4, 0, 0]}>{chartData.map((entry) => <Cell key={entry.name} fill={entry.profit >= 0 ? "hsl(160 84% 39%)" : "hsl(0 72% 51%)"} />)}</Bar></BarChart></ResponsiveContainer>}</div>

    <div className="overflow-hidden rounded-lg border border-card-border bg-card"><table className="w-full text-sm"><thead><tr className="border-b border-border bg-secondary/50">{["Pair", "Trades", "Profit (USDT)", "Profit (%)"].map((heading) => <th key={heading} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">{heading}</th>)}</tr></thead><tbody>{performanceQuery.isLoading ? Array.from({ length: 4 }).map((_, index) => <tr key={index} className="border-b border-border/50"><td colSpan={4} className="px-4 py-3"><div className="h-4 animate-pulse rounded bg-muted" /></td></tr>) : sortedPairs.length === 0 ? <tr><td colSpan={4}><QueryEmpty message="No performance data yet — run some trades first." /></td></tr> : sortedPairs.map((pair) => <PerformanceRow key={pair.pair} pair={pair} />)}</tbody></table></div>
  </div>;
}

function PerformanceRow({ pair }: { pair: PairPerformance }) {
  return <tr className="border-b border-border/50 transition-colors hover:bg-muted/30"><td className="px-4 py-3 font-semibold">{pair.pair}</td><td className="px-4 py-3 tabular-nums text-muted-foreground">{pair.count}</td><td className={cn("px-4 py-3 font-medium tabular-nums", profitClass(pair.profit))}>{formatUsdt(pair.profit)}</td><td className={cn("px-4 py-3 font-medium tabular-nums", profitClass(pair.profit_pct))}>{formatPct(pair.profit_pct)}</td></tr>;
}
