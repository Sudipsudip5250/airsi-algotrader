/**
 * Read-only dashboard routes for Freqtrade telemetry.
 *
 * This proxy never exposes exchange credentials and never forwards order
 * endpoints. Market intelligence is treated as an advisory veto snapshot and
 * is only reported when it is complete, well-formed, and unexpired.
 */

import { readFile } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { Router } from "express";
import type { Request, Response } from "express";

const router = Router();
const FREQTRADE_URL = (process.env["FREQTRADE_API_URL"] ?? "http://localhost:8080").replace(/\/+$/, "");
const FT_USER = process.env["FREQTRADE_API_USER"];
const FT_PASS = process.env["FREQTRADE_API_PASS"];
const FT_AUTH = FT_USER && FT_PASS
  ? Buffer.from(`${FT_USER}:${FT_PASS}`).toString("base64")
  : null;
const INTELLIGENCE_PATH = process.env["INTELLIGENCE_DECISION_PATH"] ?? "bot/user_data/market_intelligence.json";
const MAX_LIMIT = 200;
const TOKEN_TTL_MS = 14 * 60 * 1000;

type UpstreamResult = { ok: boolean; data: unknown; status: number };
type IntelligenceDecision = {
  generated_at: string;
  expires_at: string;
  allow_long_entries: boolean;
  risk_level: "normal" | "guarded" | "elevated" | "high";
  confidence: number;
  reason: string;
  source_count: number;
  news_count: number;
  model: string;
  snapshot_hash: string;
  errors: string[];
};

let ftToken: string | null = null;
let ftTokenExpiry = 0;

function errorPayload(message: string): { error: string } {
  return { error: message };
}

function parseLimit(value: unknown, fallback: number): number | null {
  if (value === undefined) return fallback;
  const parsed = typeof value === "string" && /^\d+$/.test(value) ? Number(value) : NaN;
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= MAX_LIMIT ? parsed : null;
}

function intelligencePath(): string {
  return isAbsolute(INTELLIGENCE_PATH) ? INTELLIGENCE_PATH : resolve(process.cwd(), INTELLIGENCE_PATH);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseIntelligenceDecision(value: unknown): IntelligenceDecision | null {
  if (!isRecord(value)) return null;
  const required = [
    "generated_at", "expires_at", "allow_long_entries", "risk_level", "confidence",
    "reason", "source_count", "news_count", "model", "snapshot_hash", "errors",
  ];
  if (Object.keys(value).length !== required.length || required.some((key) => !(key in value))) return null;
  if (typeof value.generated_at !== "string" || typeof value.expires_at !== "string") return null;
  if (typeof value.allow_long_entries !== "boolean") return null;
  if (!["normal", "guarded", "elevated", "high"].includes(value.risk_level as string)) return null;
  if (typeof value.confidence !== "number" || !Number.isFinite(value.confidence) || value.confidence < 0 || value.confidence > 1) return null;
  if (typeof value.reason !== "string" || typeof value.model !== "string" || typeof value.snapshot_hash !== "string") return null;
  const sourceCount = value.source_count;
  const newsCount = value.news_count;
  if (typeof sourceCount !== "number" || !Number.isInteger(sourceCount) || sourceCount < 0 || typeof newsCount !== "number" || !Number.isInteger(newsCount) || newsCount < 0) return null;
  if (!Array.isArray(value.errors) || value.errors.some((error) => typeof error !== "string")) return null;
  const hasTimezone = (timestamp: string) => /(Z|[+-]\d{2}:?\d{2})$/.test(timestamp);
  const generated = Date.parse(value.generated_at);
  const expires = Date.parse(value.expires_at);
  if (!hasTimezone(value.generated_at) || !hasTimezone(value.expires_at) || !Number.isFinite(generated) || !Number.isFinite(expires) || expires <= Date.now()) return null;
  return value as unknown as IntelligenceDecision;
}

async function getFtToken(forceRefresh = false): Promise<string | null> {
  if (!FT_AUTH) return null;
  if (!forceRefresh && ftToken && Date.now() < ftTokenExpiry) return ftToken;
  try {
    const response = await fetch(`${FREQTRADE_URL}/api/v1/token/login`, {
      method: "POST",
      headers: { Authorization: `Basic ${FT_AUTH}`, Accept: "application/json" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return null;
    const data = await response.json() as { access_token?: unknown };
    if (typeof data.access_token !== "string" || data.access_token.length === 0) return null;
    ftToken = data.access_token;
    ftTokenExpiry = Date.now() + TOKEN_TTL_MS;
    return ftToken;
  } catch {
    return null;
  }
}

async function ftGet(path: string): Promise<UpstreamResult> {
  const request = async (token: string | null): Promise<UpstreamResult> => {
    if (!token) return { ok: false, data: errorPayload("Bot offline or not configured"), status: 503 };
    try {
      const response = await fetch(`${FREQTRADE_URL}/api/v1${path}`, {
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
        signal: AbortSignal.timeout(10_000),
      });
      const text = await response.text();
      let data: unknown = null;
      if (text.trim()) {
        try {
          data = JSON.parse(text);
        } catch {
          data = errorPayload("Bot returned an invalid response");
        }
      }
      return { ok: response.ok, data, status: response.status };
    } catch {
      return { ok: false, data: errorPayload("Bot unreachable"), status: 503 };
    }
  };

  const firstToken = await getFtToken();
  const first = await request(firstToken);
  if (first.status !== 401 || !FT_AUTH) return first;
  ftToken = null;
  ftTokenExpiry = 0;
  return request(await getFtToken(true));
}

function sendUpstream(res: Response, result: UpstreamResult): void {
  res.status(result.status).json(result.data);
}

router.get("/bot/status", async (_req: Request, res: Response) => {
  const result = await ftGet("/status");
  if (!result.ok) {
    res.status(result.status).json({ online: false, mode: "offline", trades: [], error: result.data });
    return;
  }
  res.json({ online: true, mode: "running", trades: Array.isArray(result.data) ? result.data : [] });
});

router.get("/bot/ping", async (_req: Request, res: Response) => {
  try {
    const response = await fetch(`${FREQTRADE_URL}/api/v1/ping`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(3_000),
    });
    const text = await response.text();
    let data: unknown = {};
    try { data = text.trim() ? JSON.parse(text) : {}; } catch { data = {}; }
    res.json({ online: response.ok, ...(isRecord(data) ? data : {}) });
  } catch {
    res.json({ online: false });
  }
});

router.get("/bot/performance", async (_req: Request, res: Response) => sendUpstream(res, await ftGet("/performance")));
router.get("/bot/profit", async (_req: Request, res: Response) => sendUpstream(res, await ftGet("/profit")));
router.get("/bot/balance", async (_req: Request, res: Response) => sendUpstream(res, await ftGet("/balance")));
router.get("/bot/config", async (_req: Request, res: Response) => {
  const result = await ftGet("/show_config");
  if (!result.ok) return sendUpstream(res, result);
  const data = isRecord(result.data) ? result.data : {};
  const exchange = isRecord(data.exchange) ? data.exchange.name : data.exchange;
  res.json({
    strategy: typeof data.strategy === "string" ? data.strategy : null,
    state: typeof data.state === "string" ? data.state : null,
    dry_run: typeof data.dry_run === "boolean" ? data.dry_run : null,
    stake_currency: typeof data.stake_currency === "string" ? data.stake_currency : null,
    stake_amount: typeof data.stake_amount === "number" ? data.stake_amount : null,
    max_open_trades: typeof data.max_open_trades === "number" ? data.max_open_trades : null,
    timeframe: typeof data.timeframe === "string" ? data.timeframe : null,
    exchange: typeof exchange === "string" ? exchange : null,
  });
});

router.get("/bot/trades", async (req: Request, res: Response) => {
  const limit = parseLimit(req.query["limit"], 50);
  if (limit === null) return res.status(400).json(errorPayload(`limit must be an integer between 1 and ${MAX_LIMIT}`));
  return sendUpstream(res, await ftGet(`/trades?limit=${limit}`));
});

router.get("/bot/logs", async (req: Request, res: Response) => {
  const limit = parseLimit(req.query["limit"], 100);
  if (limit === null) return res.status(400).json(errorPayload(`limit must be an integer between 1 and ${MAX_LIMIT}`));
  return sendUpstream(res, await ftGet(`/logs?limit=${limit}`));
});

router.get("/bot/intelligence", async (_req: Request, res: Response) => {
  try {
    const raw = await readFile(intelligencePath(), "utf8");
    const decision = parseIntelligenceDecision(JSON.parse(raw));
    if (!decision) return res.json({ available: false, decision: null });
    return res.json({ available: true, decision });
  } catch {
    return res.json({ available: false, decision: null });
  }
});

export default router;
