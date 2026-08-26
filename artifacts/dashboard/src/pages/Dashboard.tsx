import { useBotBalance, useBotConfig, useBotIntelligence, useBotProfit, useBotStatus } from "@workspace/api-client-react";
import type { OpenTrade } from "@workspace/api-client-react";
import { Activity, AlertCircle, Clock, Target, TrendingDown, TrendingUp, Trophy, Wallet } from "lucide-react";
import { cn, formatDate, formatPct, formatUsdt, profitClass } from "@/lib/utils";
import { QueryError } from "@/components/QueryState";

function StatCard({ label, value, sub, icon: Icon, accent = false }: {
  label: string; value: string; sub?: string; icon: React.ElementType; accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-card-border bg-card p-4">
      <div className="mb-3 flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <div className={cn("flex h-7 w-7 items-center justify-center rounded-md", accent ? "bg-primary/15" : "bg-secondary")}>
          <Icon className={cn("h-3.5 w-3.5", accent ? "text-primary" : "text-muted-foreground")} />
        </div>
      </div>
      <p className="text-xl font-bold tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function OpenTradeRow({ trade }: { trade: OpenTrade }) {
  const positive = trade.profit_pct >= 0;
  return (
    <div className="flex items-center justify-between border-b border-border/50 py-3 last:border-0">
      <div className="flex items-center gap-3">
        <div className={cn("h-2 w-2 rounded-full", positive ? "bg-chart-1" : "bg-destructive")} />
        <div>
          <p className="text-sm font-semibold">{trade.pair}</p>
          <p className="text-xs text-muted-foreground">
            Entry: <span className="tabular-nums">${trade.open_rate.toFixed(4)}</span> · {formatDate(trade.open_date)}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className={cn("text-sm font-bold tabular-nums", profitClass(trade.profit_pct))}>{formatPct(trade.profit_pct)}</p>
        <p className={cn("text-xs tabular-nums", profitClass(trade.profit_abs))}>{formatUsdt(trade.profit_abs)}</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const statusQuery = useBotStatus();
  const profitQuery = useBotProfit();
  const balanceQuery = useBotBalance();
  const configQuery = useBotConfig();
  const intelligenceQuery = useBotIntelligence();
  const { data: status } = statusQuery;
  const { data: profit } = profitQuery;
  const { data: balance } = balanceQuery;
  const { data: config } = configQuery;
  const { data: intelligence } = intelligenceQuery;

  const trades = status?.trades ?? [];
  const openCount = trades.length;
  const winCount = profit?.winning_trades ?? 0;
  const loseCount = profit?.losing_trades ?? 0;
  const tradeCount = profit?.trade_count ?? 0;
  const winRate = tradeCount > 0 ? `${((winCount / tradeCount) * 100).toFixed(1)}%` : "—";
  const decision = intelligence?.decision;

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6">
        <div className="mb-1 flex items-center gap-2">
          <h1 className="text-xl font-bold">Dashboard</h1>
          {config?.dry_run && <span className="rounded-full border border-amber-500/20 bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400">Paper Trading</span>}
        </div>
        <p className="text-sm text-muted-foreground">{config?.strategy ?? "—"} · {config?.timeframe ?? "—"} · {config?.stake_currency ?? "USDT"}</p>
      </div>

      {statusQuery.isError && <div className="mb-4"><QueryError /></div>}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Total P&L" value={formatUsdt(profit?.profit_closed_coin)} sub={formatPct(profit?.profit_closed_percent)} icon={profit?.profit_closed_coin != null && profit.profit_closed_coin >= 0 ? TrendingUp : TrendingDown} accent />
        <StatCard label="Open Trades" value={String(openCount)} sub={`Max: ${config?.max_open_trades ?? "—"}`} icon={Activity} />
        <StatCard label="Win Rate" value={winRate} sub={`${winCount}W / ${loseCount}L of ${tradeCount}`} icon={Target} />
        <StatCard label="Wallet" value={balance?.total != null ? `${balance.total.toFixed(2)} USDT` : "—"} sub={balance?.stake ?? undefined} icon={Wallet} />
      </div>

      <div className="mb-4 rounded-lg border border-card-border bg-card p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Market intelligence gate</h2>
            <p className="mt-1 text-xs text-muted-foreground">Advisory-only risk snapshot; it can veto new entries but cannot place or close trades.</p>
          </div>
          <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", decision?.allow_long_entries ? "bg-primary/15 text-primary" : "bg-destructive/15 text-destructive")}>
            {intelligence?.available && decision ? decision.risk_level : "unavailable"}
          </span>
        </div>
        {decision && <p className="mt-3 text-xs text-muted-foreground">{decision.reason} · expires {formatDate(decision.expires_at)}</p>}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-card-border bg-card p-4">
          <div className="mb-4 flex items-center justify-between"><h2 className="text-sm font-semibold">Open Positions</h2><span className="text-xs tabular-nums text-muted-foreground">{openCount} active</span></div>
          {statusQuery.isLoading ? <div className="space-y-3">{[0, 1].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}</div> : trades.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center"><Activity className="mb-2 h-8 w-8 text-muted-foreground/40" /><p className="text-sm text-muted-foreground">No open trades</p><p className="mt-0.5 text-xs text-muted-foreground/60">Bot is waiting for signals</p></div>
          ) : <div>{trades.map((trade) => <OpenTradeRow key={trade.trade_id} trade={trade} />)}</div>}
        </div>

        <div className="rounded-lg border border-card-border bg-card p-4">
          <h2 className="mb-4 text-sm font-semibold">Summary</h2>
          <div className="space-y-3">
            {[
              { label: "Best pair", value: profit?.best_pair ?? "—", icon: Trophy },
              { label: "First trade", value: formatDate(profit?.first_trade_date), icon: Clock },
              { label: "Latest trade", value: formatDate(profit?.latest_trade_date), icon: Clock },
              { label: "Avg duration", value: profit?.avg_duration ?? "—", icon: Clock },
              { label: "Stake / trade", value: config?.stake_amount != null ? `${config.stake_amount} USDT` : "—", icon: Wallet },
              { label: "Exchange", value: config?.exchange ?? "—", icon: Activity },
            ].map(({ label, value, icon: Icon }) => <div key={label} className="flex items-center justify-between text-sm"><div className="flex items-center gap-2 text-muted-foreground"><Icon className="h-3.5 w-3.5" /><span>{label}</span></div><span className="font-medium tabular-nums">{value}</span></div>)}
          </div>
          {!status?.online && <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-destructive"><AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" /><p className="text-xs">Bot is offline. Start Freqtrade to see live data.</p></div>}
          {profitQuery.isError || balanceQuery.isError || configQuery.isError || intelligenceQuery.isError ? <div className="mt-4"><QueryError message="Some telemetry is unavailable; values shown as dashes are not zeroes." /></div> : null}
        </div>
      </div>
    </div>
  );
}
