import { useState } from "react";
import { useBotTrades } from "@workspace/api-client-react";
import type { ClosedTrade } from "@workspace/api-client-react";
import { ArrowDownRight, ArrowUpRight, Search } from "lucide-react";
import { cn, formatDate, formatPct, formatUsdt, profitClass } from "@/lib/utils";
import { QueryError, QueryEmpty } from "@/components/QueryState";

export default function Trades() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError } = useBotTrades({ limit: 100 });
  const trades = data?.trades ?? [];
  const query = search.trim().toLowerCase();
  const filtered = trades.filter((trade) => `${trade.pair} ${trade.sell_reason ?? ""}`.toLowerCase().includes(query));

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div><h1 className="text-xl font-bold">Trade History</h1><p className="text-sm text-muted-foreground">{trades.length} closed trades</p></div>
        <div className="relative"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search pair or reason..." aria-label="Search trades" className="w-52 rounded-md border border-border bg-secondary py-1.5 pl-8 pr-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring" /></div>
      </div>
      {isError ? <QueryError /> : <div className="overflow-hidden rounded-lg border border-card-border bg-card"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-border bg-secondary/50">{["Pair", "Entry", "Exit", "Duration", "P&L %", "P&L USDT", "Reason"].map((heading) => <th key={heading} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">{heading}</th>)}</tr></thead><tbody>
        {isLoading ? Array.from({ length: 8 }).map((_, index) => <tr key={index} className="border-b border-border/50"><td colSpan={7} className="px-4 py-3"><div className="h-4 animate-pulse rounded bg-muted" /></td></tr>) : filtered.length === 0 ? <tr><td colSpan={7}><QueryEmpty message={search ? "No trades match your search." : "No closed trades yet."} /></td></tr> : filtered.map((trade) => <TradeRow key={trade.trade_id} trade={trade} />)}
      </tbody></table></div></div>}
    </div>
  );
}

function TradeRow({ trade }: { trade: ClosedTrade }) {
  const profit = trade.profit_pct ?? 0;
  const positive = profit >= 0;
  return <tr className="border-b border-border/50 transition-colors hover:bg-muted/30"><td className="px-4 py-3"><div className="flex items-center gap-2"><div className={cn("flex h-6 w-6 items-center justify-center rounded", positive ? "bg-chart-1/15" : "bg-destructive/15")}>{positive ? <ArrowUpRight className="h-3.5 w-3.5 text-chart-1" /> : <ArrowDownRight className="h-3.5 w-3.5 text-destructive" />}</div><span className="font-semibold">{trade.pair}</span></div></td><td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">{formatDate(trade.open_date)}<br /><span className="text-foreground">${trade.open_rate.toFixed(4)}</span></td><td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">{formatDate(trade.close_date)}<br /><span className="text-foreground">{trade.close_rate == null ? "—" : `$${trade.close_rate.toFixed(4)}`}</span></td><td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">{trade.open_date && trade.close_date ? getDuration(trade.open_date, trade.close_date) : "—"}</td><td className={cn("px-4 py-3 font-bold tabular-nums", profitClass(trade.profit_pct))}>{formatPct(trade.profit_pct)}</td><td className={cn("px-4 py-3 tabular-nums", profitClass(trade.profit_abs))}>{formatUsdt(trade.profit_abs)}</td><td className="px-4 py-3"><span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">{trade.sell_reason ?? "—"}</span></td></tr>;
}

function getDuration(open: string, close: string): string {
  const ms = new Date(close).getTime() - new Date(open).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}
