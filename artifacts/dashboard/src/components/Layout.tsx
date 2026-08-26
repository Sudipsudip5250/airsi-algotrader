import { ReactNode } from "react";
import { Link, useLocation } from "wouter";
import { useBotPing } from "@workspace/api-client-react";
import {
  LayoutDashboard,
  ArrowLeftRight,
  BarChart2,
  ScrollText,
  FlaskConical,
  Bot,
  Circle,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/trades",      icon: ArrowLeftRight, label: "Trades" },
  { href: "/performance", icon: BarChart2,      label: "Performance" },
  { href: "/logs",        icon: ScrollText,     label: "Logs" },
  { href: "/experiments", icon: FlaskConical,   label: "Experiments" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const { data: ping } = useBotPing();
  const online = ping?.online === true;

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-sidebar border-r border-sidebar-border flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-sidebar-border">
          <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-sidebar-foreground leading-none">AIRSI AlgoTrader</p>
            <p className="text-xs text-muted-foreground mt-0.5">Unified Trading Dashboard</p>
          </div>
        </div>

        {/* Status pill */}
        <div className="px-4 py-3 border-b border-sidebar-border">
          <div className={cn(
            "flex items-center gap-2 text-xs font-medium px-2.5 py-1.5 rounded-md",
            online
              ? "bg-primary/10 text-primary"
              : "bg-destructive/10 text-destructive"
          )}>
            <Circle className={cn("w-2 h-2 fill-current", online && "live-dot")} />
            {online ? "Bot Online" : "Bot Offline"}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {navItems.map(({ href, icon: Icon, label }) => {
            const active = location === href;
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-foreground font-medium"
                    : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                )}
              >
                <Icon className={cn("w-4 h-4", active ? "text-primary" : "")} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-sidebar-border">
          <p className="text-xs text-muted-foreground">Educational use only</p>
          <p className="text-xs text-muted-foreground">⚠️ Not financial advice</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
