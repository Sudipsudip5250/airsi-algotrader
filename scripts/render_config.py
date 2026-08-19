"""Render a Freqtrade JSON config template using environment variables.

Tracked config files intentionally contain placeholders such as
``${FREQTRADE_JWT_SECRET}``. Freqtrade does not expand those placeholders, so
this helper renders a local, ignored config file and fails closed when a
required variable is absent.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
from pathlib import Path

PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Freqtrade config template")
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    text = args.template.read_text()
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = os.environ.get(name, "")
        if not value:
            missing.add(name)
            return match.group(0)
        return value

    rendered = PLACEHOLDER.sub(replace, text)
    if missing:
        names = ", ".join(sorted(missing))
        raise SystemExit(f"Missing required environment variables: {names}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    args.output.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"Rendered {args.template} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
