/**
 * Bot Dashboard Routes
 * Proxies requests to the Freqtrade REST API (default: http://localhost:8080)
 * and serves combined data to the frontend dashboard.
 */

import { readFile } from "node:fs/promises";
import { Router } from "express";
import type { Request, Response } from "express";

const router = Router();

const FREQTRADE_URL = process.env["FREQTRADE_API_URL"] ?? "http://localhost:8080";
const FT_USER = process.env["FREQTRADE_API_USER"];
const FT_PASS = process.env["FREQTRADE_API_PASS"];
const FT_AUTH = FT_USER && FT_PASS
  ? Buffer.from(`${FT_USER}:${FT_PASS}`).toString("base64")
  : null;
const INTELLIGENCE_PATH = process.env["INTELLIGENCE_DECISION_PATH"] ?? "bot/user_data/market_intelligence.json";

/** Cached JWT token from Freqtrade */
let ftToken: string | null = null;
let ftTokenExpiry = 0;

async function getFtToken(): Promise<string | null> {
  if (!FT_AUTH) return null;
  if (ftToken && Date.now() < ftTokenExpiry) return ftToken;
  try {
    const resp = await fetch(`${FREQTRADE_URL}/api/v1/token/login`, {
      method: "POST",
      headers: {
        "Authorization": `Basic ${FT_AUTH}`,
        "Content-Type": "application/json",
      },
    });
    if (!resp.ok) return null;
    const data = await resp.json() as { access_token?: string };
    ftToken = data.access_token ?? null;
    ftTokenExpiry = Date.now() + 14 * 60 * 1000; // 14 min (token lasts 15)
    return ftToken;
  } catch {
    return null;
  }
}

async function ftGet(path: string): Promise<{ ok: boolean; data: unknown; status: number }> {
  const token = await getFtToken();
  if (!token) return { ok: false, data: { error: "Bot offline or not configured" }, status: 503 };
  try {
    const resp = await fetch(`${FREQTRADE_URL}/api/v1${path}`, {
      headers: { "Authorization": `Bearer ${token}` },
    });
    const data = await resp.json();
    return { ok: resp.ok, data, status: resp.status };
  } catch (err) {
    return { ok: false, data: { error: "Bot unreachable" }, status: 503 };
  }
}

/** GET /api/bot/status — bot state, uptime, running mode */
router.get("/bot/status", async (_req: Request, res: Response) => {
  const result = await ftGet("/status");
  if (!result.ok && result.status === 503) {
    res.json({ online: false, mode: "offline", trades: [] });
    return;
  }
  res.json({ online: true, trades: result.data });
});

/** GET /api/bot/ping — lightweight health check */
router.get("/bot/ping", async (_req: Request, res: Response) => {
  try {
    const resp = await fetch(`${FREQTRADE_URL}/api/v1/ping`, { signal: AbortSignal.timeout(3000) });
    const data = await resp.json();
    res.json({ online: true, ...data as object });
  } catch {
    res.json({ online: false });
  }
});

/** GET /api/bot/performance — per-pair P&L */
router.get("/bot/performance", async (_req: Request, res: Response) => {
  const result = await ftGet("/performance");
  res.status(result.status).json(result.data);
});

/** GET /api/bot/profit — overall profit summary */
router.get("/bot/profit", async (_req: Request, res: Response) => {
  const result = await ftGet("/profit");
  res.status(result.status).json(result.data);
});

/** GET /api/bot/trades — recent closed trades */
router.get("/bot/trades", async (req: Request, res: Response) => {
  const limit = req.query["limit"] ?? 50;
  const result = await ftGet(`/trades?limit=${limit}`);
  res.status(result.status).json(result.data);
});

/** GET /api/bot/balance — wallet balances */
router.get("/bot/balance", async (_req: Request, res: Response) => {
  const result = await ftGet("/balance");
  res.status(result.status).json(result.data);
});

/** GET /api/bot/logs — recent log lines */
router.get("/bot/logs", async (req: Request, res: Response) => {
  const limit = req.query["limit"] ?? 100;
  const result = await ftGet(`/logs?limit=${limit}`);
  res.status(result.status).json(result.data);
});

/** GET /api/bot/intelligence — latest read-only market-risk decision */
router.get("/bot/intelligence", async (_req: Request, res: Response) => {
  try {
    const raw = await readFile(INTELLIGENCE_PATH, "utf8");
    const decision = JSON.parse(raw) as Record<string, unknown>;
    res.json({ available: true, decision });
  } catch {
    res.json({ available: false, decision: null });
  }
});

/** GET /api/bot/config — active bot configuration (sanitized) */
router.get("/bot/config", async (_req: Request, res: Response) => {
  const result = await ftGet("/show_config");
  res.status(result.status).json(result.data);
});

export default router;
