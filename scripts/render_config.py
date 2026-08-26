"""Render a Freqtrade JSON config template with environment variables.

Tracked templates intentionally contain placeholders such as
``${FREQTRADE_JWT_SECRET}``. Freqtrade does not expand those placeholders, so
this helper creates a local, ignored config and rejects missing or placeholder
credentials before writing it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from pathlib import Path

PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
PLACEHOLDER_VALUES = {"", "your_telegram_bot_token_here", "your_telegram_chat_id_here", "your_freqtrade_api_user_here", "your_strong_freqtrade_password_here", "generate_a_random_secret_at_least_64_characters", "generate_a_random_session_secret"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Freqtrade config template")
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        text = args.template.read_text(encoding="utf-8")
        json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid config template {args.template}: {exc}") from exc

    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = os.environ.get(name, "").strip()
        if value.lower() in PLACEHOLDER_VALUES or value.startswith("<") or value.endswith("_here"):
            missing.add(name)
            return match.group(0)
        return value

    rendered = PLACEHOLDER.sub(replace, text)
    unresolved = sorted(set(PLACEHOLDER.findall(rendered)))
    missing.update(unresolved)
    if missing:
        names = ", ".join(sorted(missing))
        raise SystemExit(f"Missing or placeholder environment variables: {names}")

    try:
        json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Rendered config is invalid JSON: {exc}") from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    args.output.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"Rendered {args.template} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
