import { appendFile, mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { Router } from "express";
import type { Request, Response } from "express";

const router = Router();

function resolveArtifactRoot(): string {
  const configured = process.env["AIRSI_REPO_ROOT"];
  if (configured) return resolve(configured);
  const candidates = [process.cwd(), resolve(process.cwd(), "../..")];
  return candidates.find((candidate) => existsSync(join(candidate, "proposals")) && existsSync(join(candidate, "bot", "config.paper.json"))) ?? candidates[0];
}

const ROOT = resolveArtifactRoot();
const PROPOSALS_DIR = join(ROOT, "proposals");
const EVALUATIONS_DIR = join(ROOT, "experiments", "evaluations");
const DECISIONS_DIR = join(ROOT, "experiments", "decisions");
const PROFILES_DIR = join(ROOT, "experiments", "experimental-profiles");
const ACTION_LOG = join(ROOT, "experiments", "agent-actions.jsonl");
const PAPER_TEMPLATE = join(ROOT, "bot", "config.paper.json");
const MAX_LIMIT = 200;
const ID_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,127}$/;
const ALLOWED_DECISIONS = new Set(["approve", "reject", "request-more-data"]);
const ALLOWED_PROPOSAL_TYPES = new Set(["parameter_change", "test_idea", "documentation"]);
const ALLOWED_PROPOSAL_STATUSES = new Set(["pending", "evaluated", "approved", "rejected", "applied"]);
const ALLOWED_VERDICTS = new Set(["promising", "not_promising", "inconclusive", "not_run"]);
const ALLOWED_CONFIG_CHANGES = new Set(["max_open_trades", "stake_amount", "dry_run_wallet", "process_throttle_secs"]);

type JsonRecord = Record<string, unknown>;
type ExperimentStatus = "pending" | "approved" | "rejected" | "request-more-data" | "evaluated";
type Decision = "approve" | "reject" | "request-more-data";

type ExperimentProposal = JsonRecord & {
  proposal_id: string;
  title: string;
  hypothesis: string;
  proposal_type: string;
  target_config: string;
  created_at: string;
  status: string;
};

type EvaluationResult = JsonRecord & {
  proposal_id: string;
  verdict: string;
  baseline: JsonRecord;
  candidate: JsonRecord;
  delta: JsonRecord;
  evaluated_at: string;
};

type HumanDecision = JsonRecord & {
  proposal_id: string;
  decision: Decision;
  reviewer: string;
  rationale: string;
  decided_at: string;
  apply_to_experimental: boolean;
  applied_path: string | null;
};

type ExperimentSummary = {
  id: string;
  status: ExperimentStatus;
  proposal: ExperimentProposal;
  evaluation: EvaluationResult | null;
  decision: HumanDecision | null;
  experimental_profile: string | null;
};

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSafeId(value: string): boolean {
  return ID_PATTERN.test(value);
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function timestampValue(value: unknown): string | null {
  const text = stringValue(value);
  if (!text || text.length > 64 || (!text.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(text))) return null;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? text : null;
}

function finiteNumberMap(value: unknown): value is Record<string, number> {
  if (!isRecord(value)) return false;
  return Object.values(value).every((entry) => typeof entry === "number" && Number.isFinite(entry));
}

function safeJsonPath(directory: string, id: string): string {
  if (!isSafeId(id)) throw new Error("invalid experiment id");
  return join(directory, `${id}.json`);
}

async function readRecord(path: string): Promise<JsonRecord | null> {
  try {
    const parsed: unknown = JSON.parse(await readFile(path, "utf8"));
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function parseProposal(value: JsonRecord | null): ExperimentProposal | null {
  if (!value || value.schema_version !== 1) return null;
  const proposalId = stringValue(value.proposal_id);
  const title = stringValue(value.title);
  const hypothesis = stringValue(value.hypothesis);
  const proposalType = stringValue(value.proposal_type);
  const targetConfig = stringValue(value.target_config);
  const createdAt = timestampValue(value.created_at);
  const status = stringValue(value.status);
  if (!proposalId || !title || !hypothesis || !proposalType || !targetConfig || !createdAt || !status) return null;
  if (!isSafeId(proposalId) || !ALLOWED_PROPOSAL_TYPES.has(proposalType) || !ALLOWED_PROPOSAL_STATUSES.has(status)) return null;
  if (targetConfig === "bot/config.paper.json" || !targetConfig.startsWith("experiments/experimental-profiles/") || targetConfig.includes("config.live")) return null;
  if (!finiteNumberMap(value.changes) || !isRecord(value.evaluation_plan) || !isRecord(value.source_summary)) return null;
  return value as ExperimentProposal;
}

function parseEvaluation(value: JsonRecord | null, proposalId: string): EvaluationResult | null {
  if (!value || value.schema_version !== 1 || value.proposal_id !== proposalId) return null;
  const evaluatedAt = timestampValue(value.evaluated_at);
  const verdict = stringValue(value.verdict);
  if (!evaluatedAt || !stringValue(value.evaluator_version) || !verdict || !ALLOWED_VERDICTS.has(verdict)) return null;
  if (!finiteNumberMap(value.baseline) || !finiteNumberMap(value.candidate) || !finiteNumberMap(value.delta)) return null;
  return value as EvaluationResult;
}

function parseDecision(value: JsonRecord | null, proposalId: string): HumanDecision | null {
  if (!value || value.schema_version !== 1 || value.proposal_id !== proposalId) return null;
  const decision = stringValue(value.decision);
  const appliedPath = value.applied_path;
  if (!decision || !ALLOWED_DECISIONS.has(decision) || !timestampValue(value.decided_at) || !stringValue(value.reviewer) || !stringValue(value.rationale)) return null;
  if (typeof value.apply_to_experimental !== "boolean") return null;
  if (appliedPath !== null && (typeof appliedPath !== "string" || !appliedPath.startsWith("experiments/experimental-profiles/") || appliedPath.includes("config.live"))) return null;
  return value as HumanDecision;
}

function statusFor(evaluation: EvaluationResult | null, decision: HumanDecision | null): ExperimentStatus {
  if (decision?.decision === "approve") return "approved";
  if (decision?.decision === "reject") return "rejected";
  if (decision?.decision === "request-more-data") return "request-more-data";
  if (evaluation) return "evaluated";
  return "pending";
}

async function loadExperiment(id: string): Promise<ExperimentSummary | null> {
  if (!isSafeId(id)) return null;
  const proposal = parseProposal(await readRecord(safeJsonPath(PROPOSALS_DIR, id)));
  if (!proposal || proposal.proposal_id !== id) return null;
  const evaluation = parseEvaluation(await readRecord(safeJsonPath(EVALUATIONS_DIR, id)), id);
  const decision = parseDecision(await readRecord(safeJsonPath(DECISIONS_DIR, id)), id);
  const appliedPath = decision?.applied_path ?? null;
  return {
    id,
    status: statusFor(evaluation, decision),
    proposal,
    evaluation,
    decision,
    experimental_profile: appliedPath,
  };
}

async function listExperiments(limit: number): Promise<ExperimentSummary[]> {
  let entries: string[] = [];
  try {
    entries = await readdir(PROPOSALS_DIR);
  } catch {
    return [];
  }
  const ids = entries
    .filter((entry) => entry.endsWith(".json"))
    .map((entry) => entry.slice(0, -5))
    .filter(isSafeId)
    .slice(0, MAX_LIMIT);
  const experiments = (await Promise.all(ids.map((id) => loadExperiment(id)))).filter(
    (experiment): experiment is ExperimentSummary => experiment !== null,
  );
  experiments.sort((left, right) => right.proposal.created_at.localeCompare(left.proposal.created_at));
  return experiments.slice(0, limit);
}

function parseLimit(value: unknown): number {
  if (value === undefined) return MAX_LIMIT;
  if (typeof value !== "string" || !/^\d+$/.test(value)) return 0;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= MAX_LIMIT ? parsed : 0;
}

function bodyRecord(req: Request): JsonRecord | null {
  return isRecord(req.body) ? req.body : null;
}

function paramId(req: Request): string | null {
  const value = req.params.id;
  return typeof value === "string" ? value : null;
}

function bodyText(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized && normalized.length <= maxLength ? normalized : null;
}

async function writeJsonAtomic(path: string, payload: JsonRecord): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.tmp`;
  await writeFile(temporary, `${JSON.stringify(payload, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, path);
}

async function logDecision(decision: HumanDecision): Promise<void> {
  await mkdir(dirname(ACTION_LOG), { recursive: true });
  await appendFile(
    ACTION_LOG,
    `${JSON.stringify({
      timestamp: decision.decided_at,
      actor: "dashboard-review",
      action: "proposal_decided",
      details: {
        proposal_id: decision.proposal_id,
        decision: decision.decision,
        reviewer: decision.reviewer,
        apply_to_experimental: decision.apply_to_experimental,
        applied_path: decision.applied_path,
      },
    })}\n`,
    "utf8",
  );
}

async function createExperimentalProfile(proposal: ExperimentProposal): Promise<string> {
  const target = stringValue(proposal.target_config);
  if (!target || !target.startsWith("experiments/experimental-profiles/") || target.includes("config.live")) {
    throw new Error("proposal target is not an experimental profile");
  }
  const changes = isRecord(proposal.changes) ? proposal.changes : {};
  const unknown = Object.keys(changes).filter((key) => !ALLOWED_CONFIG_CHANGES.has(key));
  if (unknown.length > 0) throw new Error(`unsupported config changes: ${unknown.join(", ")}`);
  const template = await readRecord(PAPER_TEMPLATE);
  if (!template) throw new Error("paper profile is unavailable");
  const profile: JsonRecord = {
    ...template,
    dry_run: true,
    initial_state: "stopped",
    force_entry_enable: false,
    bot_name: `AIRSIAlgoTrader-Experiment-${proposal.proposal_id.slice(-12)}`,
  };
  for (const [key, rawValue] of Object.entries(changes)) {
    if (typeof rawValue !== "number" || !Number.isFinite(rawValue)) throw new Error(`change ${key} must be finite`);
    if (key === "max_open_trades") profile[key] = Math.max(1, Math.min(Math.trunc(rawValue), 10));
    else if (key === "process_throttle_secs") {
      const internals = isRecord(profile.internals) ? profile.internals : {};
      profile.internals = { ...internals, process_throttle_secs: Math.max(1, Math.min(Math.trunc(rawValue), 60)) };
    } else profile[key] = rawValue;
  }
  const output = safeJsonPath(PROFILES_DIR, proposal.proposal_id);
  await writeJsonAtomic(output, profile);
  return `experiments/experimental-profiles/${proposal.proposal_id}.json`;
}

router.get("/experiments", async (req: Request, res: Response) => {
  const limit = parseLimit(req.query["limit"]);
  if (limit === 0) return res.status(400).json({ error: "limit must be an integer between 1 and 200" });
  try {
    const experiments = await listExperiments(limit);
    return res.json({ experiments, total: experiments.length });
  } catch {
    return res.status(503).json({ error: "Experiment history unavailable" });
  }
});

router.get("/experiments/:id", async (req: Request, res: Response) => {
  const id = paramId(req);
  if (!id || !isSafeId(id)) return res.status(400).json({ error: "invalid experiment id" });
  const experiment = await loadExperiment(id);
  return experiment ? res.json(experiment) : res.status(404).json({ error: "Experiment not found" });
});

router.post("/experiments/:id/decision", async (req: Request, res: Response) => {
  const id = paramId(req);
  if (!id || !isSafeId(id)) return res.status(400).json({ error: "invalid experiment id" });
  const body = bodyRecord(req);
  const decisionValue = body ? bodyText(body.decision, 32) : null;
  if (!decisionValue || !ALLOWED_DECISIONS.has(decisionValue)) {
    return res.status(400).json({ error: "decision must be approve, reject, or request-more-data" });
  }
  const experiment = await loadExperiment(id);
  if (!experiment) return res.status(404).json({ error: "Experiment not found" });
  if (!experiment.evaluation) return res.status(409).json({ error: "Evaluate the proposal before recording a decision" });
  const reviewer = (body && bodyText(body.reviewer, 256)) ?? "dashboard-operator";
  const rationale = (body && bodyText(body.note, 2_000)) ?? "Decision recorded from the dashboard.";
  const shouldApply = decisionValue === "approve" && body?.apply_experimental === true;
  let appliedPath: string | null = null;
  try {
    if (shouldApply) appliedPath = await createExperimentalProfile(experiment.proposal);
    const decision: HumanDecision = {
      schema_version: 1,
      proposal_id: id,
      decided_at: new Date().toISOString(),
      reviewer,
      decision: decisionValue as Decision,
      rationale,
      apply_to_experimental: shouldApply,
      applied_path: appliedPath,
    };
    await writeJsonAtomic(safeJsonPath(DECISIONS_DIR, id), decision);
    await logDecision(decision);
    const updated = await loadExperiment(id);
    return res.status(201).json(updated);
  } catch {
    return res.status(503).json({ error: "Could not record experiment decision" });
  }
});

export default router;
