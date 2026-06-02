import { useBotStatus, useBotProfit, useBotBalance, useBotConfig } from "@workspace/api-client-react";
import { TrendingUp, TrendingDown, Wallet, Activity, Target, Clock, Trophy, AlertCircle } from "lucide-react";
import { cn, formatPct, formatUsdt, formatDate, profitClass } from "@/lib/utils";

function StatCard({ label, value, sub, icon: Icon, accent = false }: {
  label: string; value: string; sub?: string;
  icon: React.ElementType; accent?: boolean;
}) {
  return (
    <div className="bg-card border border-card-border rounded-lg p-4">
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</p>
        <div className={cn("w-7 h-7 rounded-md flex items-center justify-center",
          accent ? "bg-primary/15" : "bg-secondary"
        )}>
          <Icon className={cn("w-3.5 h-3.5", accent ? "text-primary" : "text-muted-foreground")} />
        </div>
      </div>
      <p className="text-xl font-bold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
}

function OpenTradeRow({ trade }: { trade: { trade_id: number; pair: string; open_rate: number; current_rate: number; profit_pct: number; profit_abs: number; open_date: string; stake_amount: number } }) {
  const positive = trade.profit_pct >= 0;
  return (
    <div className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
      <div className="flex items-center gap-3">
        <div className={cn("w-2 h-2 rounded-full", positive ? "bg-chart-1" : "bg-destructive")} />
        <div>
          <p className="text-sm font-semibold">{trade.pair}</p>
          <p className="text-xs text-muted-foreground">
            Entry: <span className="tabular-nums">${trade.open_rate.toFixed(4)}</span> · {formatDate(trade.open_date)}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className={cn("text-sm font-bold tabular-nums", profitClass(trade.profit_pct))}>
          {formatPct(trade.profit_pct)}
        </p>
        <p className={cn("text-xs tabular-nums", profitClass(trade.profit_abs))}>
          {formatUsdt(trade.profit_abs)}
        </p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: status, isLoading: statusLoading } = useBotStatus();
  const { data: profit } = useBotProfit();
  const { data: balance } = useBotBalance();
  const { data: config } = useBotConfig();

  const trades = (status?.trades as any[]) ?? [];
  const openCount = trades.length;
  const winCount = profit?.winning_trades ?? 0;
  const loseCount = profit?.losing_trades ?? 0;
  const tradeCount = profit?.trade_count ?? 0;
  const winRate = tradeCount > 0 ? ((winCount / tradeCount) * 100).toFixed(1) : "—";

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <h1 className="text-xl font-bold">Dashboard</h1>
          {config?.dry_run && (
            <span className="text-xs bg-amber-500/15 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-medium">
              Paper Trading
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {config?.strategy ?? "—"} · {config?.timeframe ?? "—"} · {config?.stake_currency ?? "USDT"}
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Total P&L"
          value={profit?.profit_closed_coin != null ? formatUsdt(profit.profit_closed_coin) : "—"}
          sub={formatPct(profit?.profit_closed_percent)}
          icon={profit?.profit_closed_coin && profit.profit_closed_coin >= 0 ? TrendingUp : TrendingDown}
          accent
        />
        <StatCard
          label="Open Trades"
          value={String(openCount)}
          sub={`Max: ${config?.max_open_trades ?? "—"}`}
          icon={Activity}
        />
        <StatCard
          label="Win Rate"
          value={winRate === "—" ? "—" : `${winRate}%`}
          sub={`${winCount}W / ${loseCount}L of ${tradeCount}`}
          icon={Target}
        />
        <StatCard
          label="Wallet"
          value={balance?.total != null ? `${balance.total.toFixed(2)} USDT` : "—"}
          sub={balance?.stake ?? ""}
          icon={Wallet}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Open Trades */}
        <div className="bg-card border border-card-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold">Open Positions</h2>
            <span className="text-xs text-muted-foreground tabular-nums">{openCount} active</span>
          </div>
          {statusLoading ? (
            <div className="space-y-3">
              {[0,1].map(i => (
                <div key={i} className="h-12 rounded bg-muted animate-pulse" />
              ))}
            </div>
          ) : trades.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Activity className="w-8 h-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No open trades</p>
              <p className="text-xs text-muted-foreground/60 mt-0.5">Bot is waiting for signals</p>
            </div>
          ) : (
            <div>
              {trades.map((t: any) => (
                <OpenTradeRow key={t.trade_id} trade={t} />
              ))}
            </div>
          )}
        </div>

        {/* Summary info */}
        <div className="bg-card border border-card-border rounded-lg p-4">
          <h2 className="text-sm font-semibold mb-4">Summary</h2>
          <div className="space-y-3">
            {[
              { label: "Best pair",      value: profit?.best_pair ?? "—",    icon: Trophy },
              { label: "First trade",    value: formatDate(profit?.first_trade_date), icon: Clock },
              { label: "Latest trade",   value: formatDate(profit?.latest_trade_date), icon: Clock },
              { label: "Avg duration",   value: profit?.avg_duration ?? "—",  icon: Clock },
              { label: "Stake / trade",  value: config?.stake_amount != null ? `${config.stake_amount} USDT` : "—", icon: Wallet },
              { label: "Exchange",       value: config?.exchange ?? "—",      icon: Activity },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Icon className="w-3.5 h-3.5" />
                  <span>{label}</span>
                </div>
                <span className="font-medium tabular-nums">{value}</span>
              </div>
            ))}
          </div>

          {!status?.online && (
            <div className="mt-4 flex items-start gap-2 bg-destructive/10 text-destructive border border-destructive/20 rounded-md p-3">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <p className="text-xs">Bot is offline. Start Freqtrade to see live data.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
