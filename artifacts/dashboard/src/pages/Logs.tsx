import { useState, useRef, useEffect } from "react";
import { useBotLogs } from "@workspace/api-client-react";
import { AlertCircle, Info, AlertTriangle, Bug, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

const LEVEL_MAP: Record<number, { label: string; color: string; icon: React.ElementType }> = {
  10: { label: "DEBUG",    color: "text-muted-foreground",    icon: Bug },
  20: { label: "INFO",     color: "text-blue-400",            icon: Info },
  30: { label: "WARNING",  color: "text-amber-400",           icon: AlertTriangle },
  40: { label: "ERROR",    color: "text-destructive",         icon: AlertCircle },
  50: { label: "CRITICAL", color: "text-destructive font-bold", icon: AlertCircle },
};

const levelColors: Record<string, string> = {
  DEBUG:    "text-muted-foreground",
  INFO:     "text-blue-400",
  WARNING:  "text-amber-400",
  ERROR:    "text-red-400",
  CRITICAL: "text-red-500 font-bold",
};

type LogEntry = { timestamp: number; level: number; message: string; funcname?: string };

function levelInfo(level: number) {
  return LEVEL_MAP[level] ?? { label: `L${level}`, color: "text-foreground", icon: Info };
}

export default function Logs() {
  const [filter, setFilter] = useState<"ALL" | "INFO" | "WARNING" | "ERROR">("ALL");
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, refetch, isFetching } = useBotLogs({ limit: 200 });
  const logs: LogEntry[] = (data as any)?.logs ?? [];

  const minLevel = { ALL: 0, INFO: 20, WARNING: 30, ERROR: 40 }[filter];
  const filtered = logs.filter(l => l.level >= minLevel);

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, autoScroll]);

  return (
    <div className="p-6 max-w-6xl mx-auto flex flex-col h-full">
      <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold">Bot Logs</h1>
          <p className="text-sm text-muted-foreground">{filtered.length} entries · refreshes every 10s</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Level filter */}
          <div className="flex bg-secondary rounded-md overflow-hidden border border-border text-xs">
            {(["ALL", "INFO", "WARNING", "ERROR"] as const).map(l => (
              <button
                key={l}
                onClick={() => setFilter(l)}
                className={cn(
                  "px-3 py-1.5 font-medium transition-colors",
                  filter === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {l}
              </button>
            ))}
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-secondary border border-border rounded-md text-xs hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isFetching && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Auto-scroll toggle */}
      <div className="flex items-center gap-2 mb-3">
        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={e => setAutoScroll(e.target.checked)}
            className="accent-primary"
          />
          Auto-scroll to latest
        </label>
      </div>

      {/* Log terminal */}
      <div className="flex-1 bg-black/40 border border-border rounded-lg overflow-auto font-mono text-xs leading-relaxed p-4 min-h-96">
        {isLoading ? (
          <div className="text-muted-foreground">Loading logs...</div>
        ) : filtered.length === 0 ? (
          <div className="text-muted-foreground">
            {logs.length === 0
              ? "No logs yet. Start the bot and they will appear here."
              : "No logs match the selected level filter."}
          </div>
        ) : (
          filtered.map((log, i) => {
            const info = levelInfo(log.level);
            const Icon = info.icon;
            const ts = log.timestamp
              ? new Date(log.timestamp * 1000).toLocaleTimeString("en-US", { hour12: false })
              : "";
            return (
              <div key={i} className="flex items-start gap-2 py-0.5 hover:bg-white/5 rounded">
                <span className="text-muted-foreground/60 tabular-nums flex-shrink-0 w-20">{ts}</span>
                <Icon className={cn("w-3.5 h-3.5 flex-shrink-0 mt-0.5", info.color)} />
                <span className={cn("flex-shrink-0 w-16", info.color)}>{info.label}</span>
                <span className="text-foreground/90 break-all">{log.message}</span>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <p className="text-xs text-muted-foreground mt-2">
        Full logs also saved to: <code className="bg-secondary px-1 py-0.5 rounded">bot/user_data/logs/freqtrade.log</code>
      </p>
    </div>
  );
}
