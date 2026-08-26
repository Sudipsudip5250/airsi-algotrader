import { useEffect, useRef, useState } from "react";
import { useBotLogs } from "@workspace/api-client-react";
import type { LogLine } from "@workspace/api-client-react";
import { AlertCircle, AlertTriangle, Bug, Info, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { QueryError, QueryEmpty } from "@/components/QueryState";

const LEVEL_MAP: Record<number, { label: string; color: string; icon: React.ElementType }> = {
  10: { label: "DEBUG", color: "text-muted-foreground", icon: Bug },
  20: { label: "INFO", color: "text-blue-400", icon: Info },
  30: { label: "WARNING", color: "text-amber-400", icon: AlertTriangle },
  40: { label: "ERROR", color: "text-destructive", icon: AlertCircle },
  50: { label: "CRITICAL", color: "text-destructive font-bold", icon: AlertCircle },
};

type LogFilter = "ALL" | "INFO" | "WARNING" | "ERROR";

function levelInfo(level: number) {
  return LEVEL_MAP[level] ?? { label: `L${level}`, color: "text-foreground", icon: Info };
}

export default function Logs() {
  const [filter, setFilter] = useState<LogFilter>("ALL");
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { data, isLoading, isError, refetch, isFetching } = useBotLogs({ limit: 200 });
  const logs = data?.logs ?? [];
  const minLevel = { ALL: 0, INFO: 20, WARNING: 30, ERROR: 40 }[filter];
  const filtered = logs.filter((log) => log.level >= minLevel);

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, autoScroll]);

  return <div className="mx-auto flex h-full max-w-6xl flex-col p-6">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-xl font-bold">Bot Logs</h1><p className="text-sm text-muted-foreground">{filtered.length} entries · refreshes every 10s</p></div><div className="flex items-center gap-2"><div className="flex overflow-hidden rounded-md border border-border bg-secondary text-xs">{(["ALL", "INFO", "WARNING", "ERROR"] as const).map((level) => <button key={level} onClick={() => setFilter(level)} className={cn("px-3 py-1.5 font-medium transition-colors", filter === level ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>{level}</button>)}</div><button onClick={() => void refetch()} disabled={isFetching} className="flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs transition-colors hover:bg-muted disabled:opacity-50"><RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />Refresh</button></div></div>
    <label className="mb-3 flex cursor-pointer items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={autoScroll} onChange={(event) => setAutoScroll(event.target.checked)} className="accent-primary" />Auto-scroll to latest</label>
    {isError ? <QueryError /> : <div className="min-h-96 flex-1 overflow-auto rounded-lg border border-border bg-black/40 p-4 font-mono text-xs leading-relaxed">{isLoading ? <div className="text-muted-foreground">Loading logs...</div> : filtered.length === 0 ? <QueryEmpty message={logs.length === 0 ? "No logs yet. Start the bot and they will appear here." : "No logs match the selected level filter."} /> : filtered.map((log, index) => <LogRow key={`${log.timestamp}-${index}`} log={log} />)}<div ref={bottomRef} /></div>}
    <p className="mt-2 text-xs text-muted-foreground">Full logs also saved to: <code className="rounded bg-secondary px-1 py-0.5">bot/user_data/logs/freqtrade.log</code></p>
  </div>;
}

function LogRow({ log }: { log: LogLine }) {
  const info = levelInfo(log.level);
  const Icon = info.icon;
  const date = new Date(log.timestamp * 1000);
  const timestamp = Number.isFinite(date.getTime()) ? date.toLocaleTimeString("en-US", { hour12: false }) : "—";
  return <div className="flex items-start gap-2 rounded py-0.5 hover:bg-white/5"><span className="w-20 flex-shrink-0 tabular-nums text-muted-foreground/60">{timestamp}</span><Icon className={cn("mt-0.5 h-3.5 w-3.5 flex-shrink-0", info.color)} /><span className={cn("w-16 flex-shrink-0", info.color)}>{info.label}</span><span className="break-all text-foreground/90">{log.message}</span></div>;
}
