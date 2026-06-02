import { useState } from "react";
import { useBotTrades } from "@workspace/api-client-react";
import { ArrowUpRight, ArrowDownRight, Search } from "lucide-react";
import { cn, formatPct, formatUsdt, formatDate, profitClass } from "@/lib/utils";

export default function Trades() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useBotTrades({ limit: 100 });
  const trades = (data as any)?.trades ?? [];

  const filtered = trades.filter((t: any) =>
    t.pair?.toLowerCase().includes(search.toLowerCase()) ||
    t.sell_reason?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">Trade History</h1>
          <p className="text-sm text-muted-foreground">{trades.length} closed trades</p>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search pair or reason..."
            className="pl-8 pr-3 py-1.5 text-sm bg-secondary border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-ring w-52"
          />
        </div>
      </div>

      <div className="bg-card border border-card-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/50">
                {["Pair", "Entry", "Exit", "Duration", "P&L %", "P&L USDT", "Reason"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-border/50">
                    <td colSpan={7} className="px-4 py-3">
                      <div className="h-4 bg-muted rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground text-sm">
                    {search ? "No trades match your search." : "No closed trades yet."}
                  </td>
                </tr>
              ) : (
                filtered.map((t: any) => {
                  const profit = t.profit_pct ?? 0;
                  const positive = profit >= 0;
                  return (
                    <tr key={t.trade_id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className={cn("w-6 h-6 rounded flex items-center justify-center",
                            positive ? "bg-chart-1/15" : "bg-destructive/15"
                          )}>
                            {positive
                              ? <ArrowUpRight className="w-3.5 h-3.5 text-chart-1" />
                              : <ArrowDownRight className="w-3.5 h-3.5 text-destructive" />
                            }
                          </div>
                          <span className="font-semibold">{t.pair}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 tabular-nums text-muted-foreground text-xs">
                        {formatDate(t.open_date)}<br />
                        <span className="text-foreground">${t.open_rate?.toFixed(4) ?? "—"}</span>
                      </td>
                      <td className="px-4 py-3 tabular-nums text-muted-foreground text-xs">
                        {formatDate(t.close_date)}<br />
                        <span className="text-foreground">${t.close_rate?.toFixed(4) ?? "—"}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
                        {t.open_date && t.close_date
                          ? getDuration(t.open_date, t.close_date)
                          : "—"}
                      </td>
                      <td className={cn("px-4 py-3 font-bold tabular-nums", profitClass(t.profit_pct))}>
                        {formatPct(t.profit_pct)}
                      </td>
                      <td className={cn("px-4 py-3 tabular-nums", profitClass(t.profit_abs))}>
                        {formatUsdt(t.profit_abs)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-secondary px-2 py-0.5 rounded text-muted-foreground font-mono">
                          {t.sell_reason ?? "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function getDuration(open: string, close: string): string {
  const ms = new Date(close).getTime() - new Date(open).getTime();
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
