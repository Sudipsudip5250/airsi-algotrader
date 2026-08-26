import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FlaskConical,
  Loader2,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  useDecideExperiment,
  useListExperiments,
} from "@workspace/api-client-react";
import type {
  ExperimentDecisionInput,
  ExperimentSummary,
} from "@workspace/api-client-react";
import { QueryEmpty, QueryError } from "@/components/QueryState";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<ExperimentSummary["status"], string> = {
  pending: "bg-secondary text-muted-foreground",
  evaluated: "bg-blue-500/10 text-blue-300",
  approved: "bg-emerald-500/10 text-emerald-300",
  rejected: "bg-destructive/10 text-destructive",
  "request-more-data": "bg-amber-500/10 text-amber-300",
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : value;
}

function formatMetric(value: number | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(4) : "—";
}

function Metric({ label, value, tone }: { label: string; value: number | undefined; tone?: string }) {
  return (
    <div className="rounded-md border border-border/70 bg-background/40 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold tabular-nums", tone)}>{formatMetric(value)}</p>
    </div>
  );
}

function Metrics({ experiment }: { experiment: ExperimentSummary }) {
  const evaluation = experiment.evaluation;
  if (!evaluation) {
    return <p className="rounded-md bg-secondary/50 p-3 text-xs text-muted-foreground">No evaluation artifact is available. A human decision is blocked until the offline evaluator has run.</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      <Metric label="Baseline expectancy" value={evaluation.baseline.expectancy} />
      <Metric label="Candidate expectancy" value={evaluation.candidate.expectancy} tone="text-primary" />
      <Metric label="Expectancy delta" value={evaluation.delta.expectancy} tone={evaluation.delta.expectancy >= 0 ? "text-emerald-300" : "text-amber-300"} />
      <Metric label="Baseline drawdown" value={evaluation.baseline.max_drawdown} />
      <Metric label="Candidate drawdown" value={evaluation.candidate.max_drawdown} />
      <Metric label="Trades" value={evaluation.candidate.number_of_trades} />
    </div>
  );
}

function ExperimentCard({
  experiment,
  expanded,
  onToggle,
  note,
  onNoteChange,
  applyExperimental,
  onApplyChange,
  onDecision,
  isSubmitting,
}: {
  experiment: ExperimentSummary;
  expanded: boolean;
  onToggle: () => void;
  note: string;
  onNoteChange: (value: string) => void;
  applyExperimental: boolean;
  onApplyChange: (value: boolean) => void;
  onDecision: (decision: ExperimentDecisionInput["decision"]) => void;
  isSubmitting: boolean;
}) {
  const canDecide = Boolean(experiment.evaluation) && !experiment.decision;
  const decisionLabel = experiment.decision?.decision === "request-more-data" ? "More data requested" : experiment.decision?.decision;

  return (
    <article className="rounded-lg border border-border bg-card/60 shadow-sm transition-colors hover:border-primary/30">
      <button className="flex w-full items-start gap-3 p-4 text-left" onClick={onToggle} aria-expanded={expanded}>
        <span className="mt-0.5 text-muted-foreground">{expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium">{experiment.proposal.title}</span>
            <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium capitalize", STATUS_STYLES[experiment.status])}>{experiment.status}</span>
            {experiment.evaluation && <span className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground">{experiment.evaluation.verdict.replaceAll("_", " ")}</span>}
          </span>
          <span className="mt-1 block truncate text-xs text-muted-foreground">{experiment.id} · created {formatDate(experiment.proposal.created_at)}</span>
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border/70 px-4 pb-4 pt-3 sm:pl-11">
          <div className="grid gap-4 lg:grid-cols-[1.25fr_1fr]">
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hypothesis</p>
                <p className="mt-1 text-sm leading-relaxed">{experiment.proposal.hypothesis}</p>
              </div>
              <div className="grid gap-2 text-xs sm:grid-cols-2">
                <div className="rounded-md bg-secondary/50 p-2"><span className="text-muted-foreground">Proposal type</span><br /><span className="font-medium">{experiment.proposal.proposal_type}</span></div>
                <div className="rounded-md bg-secondary/50 p-2"><span className="text-muted-foreground">Target</span><br /><code className="break-all font-medium">{experiment.proposal.target_config}</code></div>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Proposed changes</p>
                <pre className="mt-1 overflow-auto rounded-md bg-black/30 p-3 text-xs text-foreground/80">{JSON.stringify(experiment.proposal.changes, null, 2)}</pre>
              </div>
              {experiment.decision && (
                <div className="rounded-md border border-border/70 bg-secondary/30 p-3 text-xs">
                  <p className="font-medium">Decision: <span className="capitalize">{decisionLabel}</span></p>
                  <p className="mt-1 text-muted-foreground">{experiment.decision.rationale}</p>
                  <p className="mt-1 text-muted-foreground">{experiment.decision.reviewer} · {formatDate(experiment.decision.decided_at)}</p>
                  {experiment.experimental_profile && <p className="mt-1 text-emerald-300">Stopped dry-run profile: <code>{experiment.experimental_profile}</code></p>}
                </div>
              )}
            </div>
            <div className="space-y-3">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Evaluation metrics</p>
                <Metrics experiment={experiment} />
              </div>
              {experiment.evaluation?.notes && <p className="text-xs text-muted-foreground">{experiment.evaluation.notes}</p>}
              {canDecide && (
                <div className="rounded-md border border-primary/20 bg-primary/5 p-3">
                  <p className="text-xs font-semibold">Human review required</p>
                  <p className="mt-1 text-xs text-muted-foreground">These actions only write local review artifacts. They cannot change the strategy or control an exchange.</p>
                  <textarea value={note} onChange={(event) => onNoteChange(event.target.value)} maxLength={2000} placeholder="Optional review note" className="mt-3 min-h-20 w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-xs outline-none ring-primary/40 placeholder:text-muted-foreground/70 focus:ring-2" />
                  <label className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
                    <input type="checkbox" checked={applyExperimental} onChange={(event) => onApplyChange(event.target.checked)} className="mt-0.5 accent-primary" />
                    <span>Create a <strong className="text-foreground">stopped, dry-run experimental profile</strong> on approval. The default paper/live profiles remain unchanged.</span>
                  </label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => onDecision("approve")} disabled={isSubmitting} className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"><ShieldCheck className="h-3.5 w-3.5" />Approve</button>
                    <button onClick={() => onDecision("request-more-data")} disabled={isSubmitting} className="inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-2 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-50">Request more data</button>
                    <button onClick={() => onDecision("reject")} disabled={isSubmitting} className="inline-flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-2 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"><XCircle className="h-3.5 w-3.5" />Reject</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

export default function Experiments() {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [applyExperimental, setApplyExperimental] = useState<Record<string, boolean>>({});
  const { data, isLoading, isError, isFetching, refetch } = useListExperiments({ limit: 200 });
  const decision = useDecideExperiment({
    mutation: {
      onSuccess: () => void refetch(),
    },
  });
  const experiments = data?.experiments ?? [];

  const submitDecision = (experiment: ExperimentSummary, selected: ExperimentDecisionInput["decision"]) => {
    void decision.mutateAsync({
      id: experiment.id,
      data: {
        decision: selected,
        note: notes[experiment.id] ?? null,
        apply_experimental: selected === "approve" && applyExperimental[experiment.id] === true,
      },
    });
  };

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col p-4 sm:p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2"><FlaskConical className="h-5 w-5 text-primary" /><h1 className="text-xl font-bold">Experiments</h1></div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Inspect bounded self-improvement proposals and record human decisions. Research artifacts are persistent JSON files; no action here places, cancels, sizes, or closes trades.</p>
        </div>
        <button onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-2 text-xs transition-colors hover:bg-muted disabled:opacity-50"><RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />Refresh</button>
      </div>

      {isError ? <QueryError message="Unable to load experiment history. Check the API research-artifact mount and server logs." /> : isLoading ? <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading experiment history…</div> : experiments.length === 0 ? <div className="rounded-lg border border-dashed border-border bg-card/30"><QueryEmpty message="No experiment proposals yet. Run the offline researcher and evaluator to create reviewable artifacts." /></div> : <div className="space-y-3 overflow-auto pb-4">{experiments.map((experiment) => <ExperimentCard key={experiment.id} experiment={experiment} expanded={expanded.has(experiment.id)} onToggle={() => setExpanded((current) => { const next = new Set(current); if (next.has(experiment.id)) next.delete(experiment.id); else next.add(experiment.id); return next; })} note={notes[experiment.id] ?? ""} onNoteChange={(value) => setNotes((current) => ({ ...current, [experiment.id]: value }))} applyExperimental={applyExperimental[experiment.id] === true} onApplyChange={(value) => setApplyExperimental((current) => ({ ...current, [experiment.id]: value }))} onDecision={(selected) => submitDecision(experiment, selected)} isSubmitting={decision.isPending && decision.variables?.id === experiment.id} />)}</div>}

      <p className="mt-auto border-t border-border/60 pt-3 text-xs text-muted-foreground">Educational use only. Approval creates at most a stopped dry-run experimental profile; it never promotes code or changes paper/live configuration.</p>
    </div>
  );
}
