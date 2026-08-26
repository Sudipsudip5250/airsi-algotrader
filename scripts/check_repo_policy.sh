#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

failures=0
fail() {
  printf 'POLICY FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

require_file() {
  [[ -f "$1" ]] || fail "required file is missing: $1"
}

require_text() {
  local needle=$1
  local file=$2
  grep -Fq -- "$needle" "$file" || fail "${file} does not contain required text: ${needle}"
}

require_file LICENSE
require_file README.md
require_file .github/workflows/ci.yml
require_file .github/workflows/policy.yml

require_text "educational" README.md
require_text "not financial advice" README.md
require_text "MIT License" LICENSE || true

if grep -RInE --exclude='*.md' --exclude='*.txt' --exclude='*.json' \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=venv --exclude-dir=dist \
  -- '-----BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gsk_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{12,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}' .; then
  fail "possible credential material found in source files"
fi

if grep -RInE --include='*.yml' --include='*.yaml' \
  'pull_request_target|workflow_run|self-hosted|secrets\\.|freqtrade[[:space:]]+trade|force(entry|buy|exit)|/api/v1/(start|stop)' \
  .github/workflows; then
  fail "workflow contains a privileged trigger, secret reference, self-hosted runner, or exchange-control operation"
fi

if grep -RInE --include='*.py' \
  '(^|[[:space:]])(ccxt|freqtrade[[:space:]]+trade)|requests\.(post|put|patch|delete)|/api/v1/(start|stop|force|trades)' \
  agents; then
  fail "self-improvement agents contain an exchange or order-control capability"
fi

while IFS= read -r line; do
  ref=${line##*@}
  ref=${ref%%[[:space:]]*}
  if [[ ! "$ref" =~ ^[0-9a-f]{40}$ ]]; then
    fail "GitHub Action is not pinned to a full commit SHA: $line"
  fi
done < <(grep -hRE '^[[:space:]]*uses:[[:space:]]+[^@[:space:]]+@[^[:space:]#]+' .github/workflows || true)

if ! grep -qE '^permissions:[[:space:]]*$' .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null; then
  fail "workflows must declare an explicit least-privilege permissions block"
fi

if ! grep -q 'persist-credentials: false' .github/workflows/ci.yml; then
  fail "CI checkout must disable persisted Git credentials"
fi

if ! grep -q 'python -m pytest bot/tests/' .github/workflows/ci.yml; then
  fail "CI must run the Python test suite"
fi

if ! grep -q 'pnpm run typecheck' .github/workflows/ci.yml || ! grep -q 'pnpm run build' .github/workflows/ci.yml; then
  fail "CI must run TypeScript typechecks and production builds"
fi

if (( failures > 0 )); then
  printf '%s policy check(s) failed.\n' "$failures" >&2
  exit 1
fi

printf 'repository policy checks passed\n'
