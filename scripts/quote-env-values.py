from __future__ import annotations

import shlex
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = PROJECT_ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines()
    quoted: list[str] = []
    changed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            quoted.append(line)
            continue
        key, value = line.split("=", 1)
        clean_value = value.strip()
        if _is_already_quoted(clean_value):
            quoted.append(line)
            continue
        shell_value = shlex.quote(clean_value)
        quoted.append(f"{key}={shell_value}")
        changed += int(shell_value != clean_value)
    path.write_text("\n".join(quoted) + "\n", encoding="utf-8")
    print(f"Quoted {changed} .env value(s).")


def _is_already_quoted(value: str) -> bool:
    return len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}


if __name__ == "__main__":
    main()
