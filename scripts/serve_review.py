#!/usr/bin/env python3
"""Local operator console for the file-based self-improvement queue.

This server never talks to an exchange. It only reads/writes research artifacts
under proposals/ and experiments/. Bind it to localhost or a private network.
The browser loop is propose → dry-evaluate → human decision. AI commentary and
Freqtrade backtests stay opt-in and off by default.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import DECISIONS_DIR, EVALUATIONS_DIR, PROPOSALS_DIR, collect_context, safe_artifact_path
from agents.evaluator import evaluate_proposal, persist_evaluation
from agents.models import write_json
from agents.researcher import build_proposal, find_duplicate
from agents.reviewer import decide, list_queue, load_summaries, write_queue_markdown
from agents.runtime import log_action

HOST = "0.0.0.0"
PORT = int(os.getenv("AIRSI_REVIEW_PORT", "8080"))
_TRUTHY = {"1", "true", "yes", "on"}
_MIN_MUTATION_INTERVAL_SECONDS = 2.0
_last_mutation = 0.0


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


def _seed_if_empty() -> None:
    if not _env_flag("AIRSI_REVIEW_SEED"):
        write_queue_markdown()
        return
    if load_summaries():
        write_queue_markdown()
        return
    context = collect_context()
    context["backtests"] = [
        {
            "file": "bot/user_data/backtest_results/demo.json",
            "metrics": {"expectancy": 0.04, "max_drawdown": 0.12, "number_of_trades": 18},
            "note": "demo seed for empty-queue review UI; not a live or paper result",
        }
    ]
    proposal = build_proposal(context, use_ai=False)
    if find_duplicate(str(proposal.source_summary.get("fingerprint", ""))):
        return
    path = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    write_json(path, proposal)
    result = evaluate_proposal(proposal, minimum_trades=10, run_backtest=False)
    persist_evaluation(path, result)
    log_action("review-console", "demo_seeded", proposal_id=proposal.proposal_id)
    write_queue_markdown()


def _rate_limit() -> str | None:
    global _last_mutation
    now = time.monotonic()
    if now - _last_mutation < _MIN_MUTATION_INTERVAL_SECONDS:
        return "rate limited; wait a moment before the next research action"
    _last_mutation = now
    return None


def _propose(use_ai: bool) -> dict:
    if use_ai and not _env_flag("AIRSI_REVIEW_ALLOW_AI"):
        use_ai = False
    context = collect_context()
    proposal = build_proposal(context, use_ai=use_ai)
    fingerprint = str(proposal.source_summary.get("fingerprint", ""))
    duplicate = find_duplicate(fingerprint)
    if duplicate is not None:
        return {
            "skipped": True,
            "reason": "duplicate_active_proposal",
            "existing_proposal_id": duplicate.proposal_id,
            "fingerprint": fingerprint,
        }
    output = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    write_json(output, proposal)
    log_action(
        "review-console",
        "proposal_created",
        proposal_id=proposal.proposal_id,
        use_ai=use_ai,
        ai_provider=proposal.source_summary.get("ai_provider"),
        ai_cost_class=proposal.source_summary.get("ai_cost_class"),
    )
    return {"skipped": False, "proposal": proposal.to_dict()}


def _evaluate(proposal_id: str) -> dict:
    proposal_path = safe_artifact_path(PROPOSALS_DIR, f"{proposal_id}.json")
    from agents.models import ExperimentProposal, read_json

    proposal = read_json(proposal_path, ExperimentProposal)
    result = evaluate_proposal(proposal, minimum_trades=10, run_backtest=False)
    persist_evaluation(proposal_path, result)
    log_action(
        "review-console",
        "proposal_evaluated",
        proposal_id=proposal.proposal_id,
        verdict=result.verdict,
        run_backtest=False,
    )
    return result.to_dict()


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AIRSI AlgoTrader · Experiment review</title>
  <style>
    :root {
      --bg: #07120e; --panel: #0d1c16; --line: #1f3b2e; --text: #e7f6ee;
      --muted: #8eaa9a; --accent: #3dd68c; --warn: #e7c36a; --danger: #f07178;
      --blue: #7db7ff; --chip: #163325;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); }
    header { padding: 20px 24px 12px; border-bottom: 1px solid var(--line); }
    h1 { font-size: 22px; margin: 0 0 6px; letter-spacing: -0.02em; }
    .sub { color: var(--muted); font-size: 13px; max-width: 860px; line-height: 1.5; }
    .banner { margin: 16px 24px 0; padding: 12px 14px; border: 1px solid #5a4a1a; background: #1a1608; color: var(--warn); border-radius: 10px; font-size: 13px; line-height: 1.45; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 16px 24px 0; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; padding: 14px 24px 0; }
    .stat { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
    .stat b { display: block; font-size: 20px; }
    .stat span { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
    .filters { display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 24px 0; }
    .filter, button { border: 0; border-radius: 8px; padding: 10px 12px; font-weight: 600; cursor: pointer; min-height: 44px; }
    .filter { background: #13241c; color: var(--muted); }
    .filter.on { background: var(--chip); color: var(--accent); }
    main { padding: 18px 24px 40px; display: grid; gap: 14px; }
    article { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
    .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .pill { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; padding: 3px 8px; border-radius: 999px; background: var(--chip); color: var(--accent); }
    .pill.warn { background: #2a2410; color: var(--warn); }
    .pill.danger { background: #2a1214; color: var(--danger); }
    .pill.blue { background: #132033; color: var(--blue); }
    h2 { font-size: 16px; margin: 8px 0; }
    p, li { color: var(--muted); font-size: 13px; line-height: 1.5; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin: 12px 0; }
    .metric { background: #08140f; border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
    .metric b { display: block; font-size: 16px; color: var(--text); }
    .metric span { font-size: 11px; color: var(--muted); }
    textarea, input[type=text] { width: 100%; background: #08140f; color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 10px; font: inherit; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .approve { background: var(--accent); color: #062314; }
    .more { background: #2a2410; color: var(--warn); }
    .reject { background: #3a1518; color: var(--danger); }
    .ghost { background: #13241c; color: var(--text); }
    label { font-size: 12px; color: var(--muted); display: flex; gap: 8px; align-items: flex-start; margin-top: 8px; }
    code { color: var(--accent); }
    footer { padding: 0 24px 24px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .error { margin: 12px 24px 0; padding: 10px 12px; border-radius: 8px; background: #2a1214; color: var(--danger); display: none; }
    pre { overflow: auto; background: #08140f; border-radius: 8px; padding: 10px; font-size: 12px; color: #cde8d8; }
  </style>
</head>
<body>
  <header>
    <h1>AIRSI experiment review</h1>
    <p class="sub">Human-gated research queue. Proposals cannot place, cancel, size, or leverage trades, and they cannot edit <code>AIRSIAlgoStrategy.py</code> or default paper/live configs. Education and research only — not financial advice.</p>
  </header>
  <div class="banner">Paper trading is the default. Approval may create only a <strong>stopped, dry-run</strong> experimental profile. Create Proposal and Evaluate stay on the free, no-network path. Paid models stay off unless <code>AI_ALLOW_PAID=1</code>.</div>
  <div id="error" class="error"></div>
  <div class="toolbar">
    <button class="ghost" id="propose">Create proposal (no AI)</button>
    <button class="ghost" id="refresh">Refresh</button>
  </div>
  <section class="stats" id="stats"></section>
  <div class="filters" id="filters"></div>
  <main id="list"><p>Loading queue…</p></main>
  <footer>Artifacts: proposals/, experiments/evaluations/, experiments/decisions/. Strategy remains deterministic. Terminal approve/reject decisions cannot be overwritten.</footer>
  <script>
    const escape = (value) => String(value ?? '').replace(/[&<>"'`]/g, (char) => ({
      '&': '&', '<': '<', '>': '>', '"': '"', "'": '&#39;', '`': '&#96;'
    }[char]));
    const filters = ['all', 'pending', 'evaluated', 'request-more-data', 'approved', 'rejected'];
    let activeFilter = 'all';
    let cache = [];
    const pillClass = (status) => {
      if (String(status).includes('reject') || status === 'not_promising') return 'danger';
      if (String(status).includes('data') || status === 'inconclusive' || status === 'not_run') return 'warn';
      if (String(status).includes('approv') || status === 'applied' || status === 'promising') return '';
      return 'blue';
    };
    const pill = (status) => `<span class="pill ${pillClass(status)}">${escape(status)}</span>`;
    const num = (value) => (typeof value === 'number' && Number.isFinite(value) ? value.toFixed(4) : '—');
    const evalKind = (evaluation) => {
      if (!evaluation) return 'Not evaluated';
      const version = evaluation.evaluator_version || '';
      if (evaluation.verdict === 'not_run') return 'Limited backtest (not run)';
      if (version.indexOf('limited-backtest') >= 0) return 'Limited backtest';
      return 'Dry evaluation';
    };
    const showError = (message) => {
      const node = document.getElementById('error');
      node.style.display = message ? 'block' : 'none';
      node.textContent = message || '';
    };
    const counts = (items) => items.reduce((acc, item) => {
      acc.all += 1;
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    }, { all: 0 });
    function render() {
      const stats = counts(cache);
      document.getElementById('stats').innerHTML = [
        ['All', stats.all],
        ['Pending', stats.pending || 0],
        ['Evaluated', stats.evaluated || 0],
        ['Need data', stats['request-more-data'] || 0],
        ['Approved', stats.approved || 0],
        ['Rejected', stats.rejected || 0],
      ].map(([label, value]) => `<div class="stat"><span>${label}</span><b>${value}</b></div>`).join('');
      document.getElementById('filters').innerHTML = filters.map((name) =>
        `<button class="filter ${activeFilter === name ? 'on' : ''}" data-filter="${name}">${name}</button>`
      ).join('');
      document.querySelectorAll('[data-filter]').forEach((button) => {
        button.onclick = () => { activeFilter = button.dataset.filter; render(); };
      });
      const items = cache.filter((item) => activeFilter === 'all' || item.status === activeFilter);
      const root = document.getElementById('list');
      if (!items.length) {
        root.innerHTML = '<article><p>No proposals in this filter. Use <strong>Create proposal (no AI)</strong> to collect a local research idea, then Evaluate.</p></article>';
        return;
      }
      root.innerHTML = items.map((item) => {
        const evaluation = item.evaluation;
        const canEvaluate = !evaluation;
        const canDecide = evaluation && !item.decision;
        const canFollowUp = evaluation && item.decision && item.decision.decision === 'request-more-data';
        const summary = item.proposal.source_summary || {};
        const changes = escape(JSON.stringify(item.proposal.changes || {}, null, 2));
        return `<article>
          <div class="row">${pill(item.status)} ${evaluation ? pill(evalKind(evaluation)) : ''} ${evaluation ? pill(evaluation.verdict) : ''}
            <span class="pill">${escape(item.proposal.proposal_type)}</span>
            <span class="pill blue">${escape(summary.ai_provider || 'none')} / ${escape(summary.ai_cost_class || 'free')}</span></div>
          <h2>${escape(item.proposal.title)}</h2>
          <p>${escape(item.proposal.hypothesis)}</p>
          <p>Target: <code>${escape(item.proposal.target_config)}</code></p>
          <pre>${changes}</pre>
          ${evaluation ? `<div class="metrics">
            <div class="metric"><span>Baseline expectancy</span><b>${num(evaluation.baseline.expectancy)}</b></div>
            <div class="metric"><span>Candidate expectancy</span><b>${num(evaluation.candidate.expectancy)}</b></div>
            <div class="metric"><span>Baseline drawdown</span><b>${num(evaluation.baseline.max_drawdown)}</b></div>
            <div class="metric"><span>Trades</span><b>${num(evaluation.candidate.number_of_trades)}</b></div>
          </div><p>${escape(evaluation.notes || '')}</p>` : '<p>Evaluate this proposal before recording a decision. Evaluation is a dry metric comparison and does not start Freqtrade.</p>'}
          ${item.decision ? `<p>Decision: <strong>${escape(item.decision.decision)}</strong> — ${escape(item.decision.rationale)}</p>` : ''}
          ${item.experimental_profile ? `<p>Stopped dry-run profile: <code>${escape(item.experimental_profile)}</code></p>` : ''}
          ${canEvaluate ? `<div class="actions"><button class="ghost" onclick="evaluateProposal('${escape(item.id)}')">Evaluate (dry)</button></div>` : ''}
          ${canDecide || canFollowUp ? `<input type="text" id="rev-${escape(item.id)}" placeholder="Reviewer name" />
            <textarea id="note-${escape(item.id)}" placeholder="Required rationale"></textarea>
            <label><input type="checkbox" id="apply-${escape(item.id)}" /> Create a stopped dry-run experimental profile on approve (never default paper/live)</label>
            <div class="actions">
              <button class="approve" onclick="decide('${escape(item.id)}','approve')">Approve</button>
              <button class="more" onclick="decide('${escape(item.id)}','request-more-data')">Request more data</button>
              <button class="reject" onclick="decide('${escape(item.id)}','reject')">Reject</button>
            </div>` : ''}
        </article>`;
      }).join('');
    }
    async function load() {
      showError('');
      const response = await fetch('/api/experiments');
      const data = await response.json();
      cache = data.experiments || [];
      render();
    }
    async function post(url, body) {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Request failed');
      return payload;
    }
    async function evaluateProposal(id) {
      try { await post('/api/experiments/' + id + '/evaluate', {}); await load(); }
      catch (error) { showError(error.message); }
    }
    async function decide(id, decision) {
      const reviewer = document.getElementById('rev-' + id)?.value || 'operator';
      const rationale = document.getElementById('note-' + id)?.value || '';
      const apply = document.getElementById('apply-' + id)?.checked === true;
      try {
        await post('/api/experiments/' + id + '/decision', { decision, reviewer, rationale, apply_experimental: apply });
        await load();
      } catch (error) { showError(error.message); }
    }
    document.getElementById('propose').onclick = async () => {
      try {
        const result = await post('/api/experiments/propose', { use_ai: false });
        if (result.skipped) showError('Duplicate active idea skipped: ' + result.existing_proposal_id);
        await load();
      } catch (error) { showError(error.message); }
    };
    document.getElementById('refresh').onclick = load;
    load();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("review-console: " + (format % args) + "\n")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 32_000:
            raise ValueError("payload too large")
        if length <= 0:
            return {}
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("invalid json")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/experiments":
            items = load_summaries()
            self._json(200, {"experiments": items, "total": len(items)})
            return
        if path == "/healthz":
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        limited = _rate_limit() if path.endswith("/propose") or path.endswith("/evaluate") else None
        if limited:
            self._json(429, {"error": limited})
            return
        try:
            if path == "/api/experiments/propose":
                self._json(201, _propose(bool(body.get("use_ai"))))
                return
            prefix = "/api/experiments/"
            if path.startswith(prefix) and path.endswith("/evaluate"):
                experiment_id = path[len(prefix) : -len("/evaluate")]
                self._json(201, _evaluate(experiment_id))
                return
            if path.startswith(prefix) and path.endswith("/decision"):
                experiment_id = path[len(prefix) : -len("/decision")]
                decide(
                    f"{experiment_id}.json",
                    str(body.get("decision", "")),
                    str(body.get("reviewer", "operator")),
                    str(body.get("rationale", "")),
                    bool(body.get("apply_experimental")),
                )
                items = [item for item in load_summaries() if item["id"] == experiment_id]
                self._json(201, items[0] if items else {"ok": True})
                return
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(404, {"error": "not found"})


def main() -> int:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    _seed_if_empty()
    list_queue()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"AIRSI experiment review console on http://{HOST}:{PORT} (research artifacts only)")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
