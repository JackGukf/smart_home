#!/usr/bin/env python3
"""Deploy what a commit changed to the Orange Pi, and restart only what uses it.

Before this (action list C1), the post-commit hook deployed only when the
dashboard changed; on 2026-09-25 the detector, the installers, the night watch
and its unit were copied and restarted by hand, each time after checking that
the board's copy was not something newer. This does all of that:

  1. Copies the files the commit changed under src/python/, scripts/ and
     deploy/systemd/user/ (not web_static/, which deploy-dashboard.sh builds).
  2. Refuses when a file on the board is neither the old nor the new version -
     an edit made on the board that the repo does not have - and shows which.
     `--force` overwrites anyway.
  3. Keeps the board's previous copies in .deploy-backups/<time>/ (the last 10);
     `--rollback` puts the newest set back and restarts what it touches.
  4. Works out which services use the changed code - no table to keep up to
     date: each unit's ExecStart, the run-*.sh it calls, the Python module that
     runs, and everything that module imports from src.python.
  5. Refreshes a changed unit file only where that unit is installed on the
     board, restarts only services that are running (the TV cast and
     llama-server are off on purpose), and never restarts a timer's oneshot job,
     which picks the new code up on its next run.
  6. Hands anything that touches the dashboard to deploy-dashboard.sh (it builds
     the assets and bumps the build), with --skip-go2rtc: go2rtc restarts only
     when its own files change, since a restart reconnects every camera.

    scripts/deploy.py                     # since the last commit the board got (the hook runs this)
    scripts/deploy.py --range A..B        # a range of commits
    scripts/deploy.py --dry-run           # show the plan, change nothing
    scripts/deploy.py --rollback          # undo the last deploy on the board
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEPLOYABLE = ("src/python/", "scripts/", "deploy/systemd/user/")
BUILT_ELSEWHERE = ("src/python/web_static/",)            # deploy-dashboard.sh builds these
DASHBOARD_UNIT = "smart-home-dashboard.service"
# Changes that only the dashboard deploy ships.
DASHBOARD_ONLY = ("src/python/web_static/", "tplink_switches.json", "deploy/polkit/")
UNIT_DIR = "deploy/systemd/user/"
BACKUP_DIR = ".deploy-backups"
BACKUPS_KEPT = 10
MODULE_REF = re.compile(r"src[./]python[./](\w+)")
SCRIPT_REF = re.compile(r"scripts/([\w.-]+\.(?:sh|py))")


# ─────────────────────────────────────────────── what uses what (no table)

def module_file(root: Path, module: str) -> Path:
    return root / "src" / "python" / f"{module}.py"


def imports_of(path: Path) -> set[str]:
    """src.python modules this file imports, anywhere in it (lazy imports too)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src.python."):
                    found.add(alias.name.split(".")[2])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "src.python":
                found.update(alias.name for alias in node.names)
            elif node.module.startswith("src.python."):
                found.add(node.module.split(".")[2])
    return found


def closure(root: Path, modules: set[str]) -> set[str]:
    """Repo-relative files of these modules and everything they import."""
    seen: set[str] = set()
    todo = list(modules)
    while todo:
        module = todo.pop()
        if module in seen or not module_file(root, module).exists():
            continue
        seen.add(module)
        todo.extend(imports_of(module_file(root, module)) - seen)
    return {f"src/python/{m}.py" for m in seen}


@dataclass
class Unit:
    name: str
    oneshot: bool = False
    deps: set[str] = field(default_factory=set)


def read_units(root: Path) -> dict[str, Unit]:
    units: dict[str, Unit] = {}
    for path in sorted((root / UNIT_DIR).glob("*.service")) + sorted((root / UNIT_DIR).glob("*.timer")):
        text = path.read_text(encoding="utf-8")
        unit = Unit(path.name, oneshot="Type=oneshot" in text, deps={f"{UNIT_DIR}{path.name}"})
        if path.suffix == ".service":
            exec_line = next((l for l in text.splitlines() if l.startswith("ExecStart=")), "")
            modules = set(MODULE_REF.findall(exec_line))
            scripts = {f"scripts/{s}" for s in SCRIPT_REF.findall(exec_line)}
            for script in list(scripts):
                script_path = root / script
                if not script_path.exists():
                    continue
                # What the script runs, not what it mentions: comments and
                # messages ("Create it with scripts/install-ai-services.sh") are not uses.
                body = "\n".join(l for l in script_path.read_text(encoding="utf-8").splitlines()
                                 if not l.lstrip().startswith("#") and "echo " not in l)
                modules |= set(MODULE_REF.findall(body))
                scripts |= {f"scripts/{s}" for s in SCRIPT_REF.findall(body)} - {script}
                if script.endswith(".py"):
                    modules |= imports_of(script_path)
            # A script a run script calls (generate-go2rtc-config.py) may import modules too.
            for script in scripts:
                if script.endswith(".py") and (root / script).exists():
                    modules |= imports_of(root / script)
            unit.deps |= {s for s in scripts if (root / s).exists()} | closure(root, modules)
        units[path.name] = unit
    return units


# ───────────────────────────────────────────────────────────────── the plan

def deployable(path: str) -> bool:
    return path.startswith(DEPLOYABLE) and not path.startswith(BUILT_ELSEWHERE) and "__pycache__" not in path


@dataclass
class Plan:
    copy: list[str] = field(default_factory=list)
    install_units: list[str] = field(default_factory=list)
    restart: list[str] = field(default_factory=list)
    dashboard: bool = False
    pip: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.copy or self.install_units or self.restart or self.dashboard or self.pip)


def make_plan(changed: list[str], units: dict[str, Unit], installed: set[str], active: set[str],
              deleted: list[str] = ()) -> Plan:
    plan = Plan()
    plan.copy = sorted(p for p in changed if deployable(p))
    plan.pip = "src/python/requirements.txt" in changed
    touched = set(changed)
    for name, unit in sorted(units.items()):
        hit = unit.deps & touched
        if not hit:
            continue
        unit_file = f"{UNIT_DIR}{name}"
        if unit_file in touched:
            if name in installed:
                plan.install_units.append(name)
            else:
                plan.notes.append(f"{name} changed but is not installed on the board - not installed")
        if name == DASHBOARD_UNIT:
            plan.dashboard = True
        elif name in active and not unit.oneshot:
            plan.restart.append(name)
        elif name.endswith(".timer") and name in active and unit_file in touched:
            plan.restart.append(name)
        elif name not in active and not unit.oneshot and name in installed:
            plan.notes.append(f"{name} uses changed files but is not running - left stopped")
    if any(p.startswith(DASHBOARD_ONLY) for p in changed):
        plan.dashboard = True
    for path in deleted:
        if deployable(path):
            plan.notes.append(f"{path} was deleted in the repo - left on the board (remove by hand if unused)")
    return plan


def conflicts(paths: list[str], board: dict[str, str | None], old: dict[str, str | None],
              new: dict[str, str | None]) -> list[str]:
    """Files on the board that are neither the version before nor after the change."""
    return [p for p in paths if board.get(p) is not None and board[p] not in {old.get(p), new.get(p)}]


# ─────────────────────────────────────────────────────────────── the board

class Board:
    def __init__(self, target: str, remote_path: str, dry_run: bool = False) -> None:
        self.target, self.path, self.dry_run = target, remote_path, dry_run

    def ssh(self, command: str, check: bool = True, capture: bool = True) -> str:
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", self.target, command],
                                capture_output=capture, text=True)
        if check and result.returncode != 0:
            raise RuntimeError(f"on the board: {command[:80]}... failed: {(result.stderr or '').strip()[-400:]}")
        return result.stdout if capture else ""

    def state(self, paths: list[str]) -> tuple[dict[str, str | None], set[str], set[str]]:
        """(sha256 of each path on the board, installed user units, active user units)."""
        quoted = " ".join(shlex.quote(p) for p in paths)
        script = (f"cd {shlex.quote(self.path)} && for f in {quoted}; do "
                  "if [ -f \"$f\" ]; then printf 'F %s %s\\n' \"$(sha256sum \"$f\" | cut -d' ' -f1)\" \"$f\"; fi; done; "
                  "for u in ~/.config/systemd/user/*.service ~/.config/systemd/user/*.timer; do "
                  "[ -e \"$u\" ] && printf 'I %s\\n' \"$(basename \"$u\")\"; done; "
                  "systemctl --user list-units --type=service,timer --state=active --plain --no-legend "
                  "| awk '{print \"A \" $1}'")
        hashes: dict[str, str | None] = {p: None for p in paths}
        installed, active = set(), set()
        for line in self.ssh(script).splitlines():
            kind, _, rest = line.partition(" ")
            if kind == "F":
                digest, _, path = rest.partition(" ")
                hashes[path] = digest
            elif kind == "I":
                installed.add(rest.strip())
            elif kind == "A":
                active.add(rest.strip())
        return hashes, installed, active


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout


def git_blob_hash(rev: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=PROJECT_ROOT, capture_output=True)
    return hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None


def version_in_history(path: str, digest: str) -> str | None:
    """Which commit had this exact file, if any: the board holding an *older*
    version is stale (never deployed since), not edited. Found on the first
    live run - deploy-dashboard.sh on the board was the 2026-09-12 version,
    because it was never in its own sync list."""
    log = git("log", "--format=%h %ad", "--date=short", "--", path)
    for line in log.splitlines():
        commit = line.split()[0]
        if git_blob_hash(commit, path) == digest:
            return line
    return None


# deploy-dashboard.sh's own output, committed with hooks off. Counting it would
# make every later deploy rebuild the dashboard.
METADATA_SUBJECT = "chore: record dashboard build cache-busting metadata"
DEPLOYED_MARK = ".deployed_commit"


def changed_files(rev_range: str) -> tuple[list[str], list[str]]:
    """(added or modified, deleted) across the range's commits, leaving out the
    build-metadata commits."""
    old, _, new = rev_range.partition("..")
    new = new or "HEAD"
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", old], cwd=PROJECT_ROOT,
                      capture_output=True).returncode != 0:
        spec = new                                                   # the first commit: everything
    else:
        spec = f"{old}..{new}"
    status: dict[str, str] = {}
    for commit in git("rev-list", "--reverse", spec).split():
        if git("log", "-1", "--format=%s", commit).strip() == METADATA_SUBJECT:
            continue
        for line in git("diff-tree", "--no-commit-id", "-r", "--name-status", "--no-renames", "--root",
                        commit).splitlines():
            kind, _, path = line.partition("\t")
            status[path] = kind
    changed = sorted(p for p, k in status.items() if not k.startswith("D"))
    deleted = sorted(p for p, k in status.items() if k.startswith("D"))
    return changed, deleted


def default_range(board: "Board") -> str:
    """From the last commit the board received to HEAD, so a refused or failed
    deploy is caught up by the next one instead of leaving a hole."""
    mark = board.ssh(f"cat {shlex.quote(board.path)}/{DEPLOYED_MARK} 2>/dev/null", check=False).strip()
    if mark and subprocess.run(["git", "merge-base", "--is-ancestor", mark, "HEAD"], cwd=PROJECT_ROOT,
                               capture_output=True).returncode == 0:
        return f"{mark}..HEAD"
    return "HEAD~1..HEAD"


def restart(board: Board, unit: str) -> bool:
    board.ssh(f"systemctl --user reset-failed {unit} >/dev/null 2>&1; systemctl --user restart {unit}", check=False)
    for _ in range(4):
        time.sleep(3)
        if board.ssh(f"systemctl --user is-active {unit}", check=False).strip() == "active":
            print(f"    {unit}: active")
            return True
    print(f"ERROR: {unit} did not come back:", file=sys.stderr)
    print(board.ssh(f"journalctl --user -u {unit} -n 15 --no-pager -o cat", check=False), file=sys.stderr)
    return False


def backup(board: Board, paths: list[str], existing: dict[str, str | None]) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    there = [p for p in paths if existing.get(p)]
    new = [p for p in paths if not existing.get(p)]
    target = f"{BACKUP_DIR}/{stamp}"
    board.ssh(f"cd {shlex.quote(board.path)} && mkdir -p {target} && "
              + (f"cp -p --parents {' '.join(shlex.quote(p) for p in there)} {target}/ && " if there else "")
              + f"printf '%s\\n' {' '.join(shlex.quote(p) for p in new) or chr(39) + chr(39)} > {target}/NEW_FILES && "
              f"ls -1d {BACKUP_DIR}/*/ | head -n -{BACKUPS_KEPT} | xargs -r rm -rf")
    return target


def execute(plan: Plan, board: Board, force: bool, board_hashes: dict[str, str | None]) -> int:
    if plan.copy:
        stamp = backup(board, plan.copy, board_hashes)
        print(f"==> Board's previous copies kept in {stamp}")
        files = "\n".join(plan.copy).encode()
        subprocess.run(["rsync", "--checksum", "-a", "--files-from=-", f"{PROJECT_ROOT}/",
                        f"{board.target}:{board.path}/"], input=files, check=True)
        print(f"==> Copied {len(plan.copy)} file(s)")
    if plan.pip:
        print("==> requirements.txt changed: installing into .venv")
        board.ssh(f"cd {shlex.quote(board.path)} && .venv/bin/pip install -q -r src/python/requirements.txt")
    if plan.install_units:
        units = " ".join(f"{UNIT_DIR}{u}" for u in plan.install_units)
        board.ssh(f"cd {shlex.quote(board.path)} && cp {units} ~/.config/systemd/user/ && systemctl --user daemon-reload")
        print(f"==> Unit files refreshed: {', '.join(plan.install_units)}")
    ok = True
    for unit in plan.restart:
        ok = restart(board, unit) and ok
    if plan.dashboard:
        print("==> The dashboard is affected: deploy-dashboard.sh --skip-go2rtc")
        ok = subprocess.run(["bash", str(PROJECT_ROOT / "scripts" / "deploy-dashboard.sh"), "--skip-go2rtc"],
                            cwd=PROJECT_ROOT).returncode == 0 and ok
    return 0 if ok else 1


def show(plan: Plan) -> None:
    print("Plan:")
    print("  copy:      " + (", ".join(plan.copy) or "-"))
    print("  units:     " + (", ".join(plan.install_units) or "-"))
    print("  restart:   " + (", ".join(plan.restart) or "-"))
    print("  dashboard: " + ("deploy-dashboard.sh" if plan.dashboard else "-"))
    if plan.pip:
        print("  pip:       requirements.txt")
    for note in plan.notes:
        print("  note:      " + note)


def rollback(board: Board, units: dict[str, Unit], dry_run: bool) -> int:
    newest = board.ssh(f"cd {shlex.quote(board.path)} && ls -1d {BACKUP_DIR}/*/ 2>/dev/null | tail -n 1", check=False).strip()
    if not newest:
        print("No deploy backups on the board.")
        return 1
    listing = board.ssh(f"cd {shlex.quote(board.path)}/{newest} && find . -type f ! -name NEW_FILES | sed 's#^./##'; "
                        "echo '--new--'; cat NEW_FILES 2>/dev/null")
    restored, _, new = listing.partition("--new--")
    restored_files = [l for l in restored.splitlines() if l.strip()]
    new_files = [l for l in new.splitlines() if l.strip()]
    _, installed, active = board.state([])
    plan = make_plan(restored_files + new_files, units, installed, active)
    plan.copy = []                                 # put back from the backup, not copied from here
    print(f"Rolling back {newest}:")
    print("  restore:   " + (", ".join(restored_files) or "-"))
    print("  remove:    " + (", ".join(new_files) or "-") + "  (new in that deploy)")
    show(plan)
    if dry_run:
        return 0
    board.ssh(f"cd {shlex.quote(board.path)} && "
              + (f"cp -p -r {newest}. ./ && rm -f ./NEW_FILES && " if restored_files else "")
              + (f"rm -f {' '.join(shlex.quote(p) for p in new_files)} && " if new_files else "")
              + f"rm -rf {newest}")
    board.ssh(f"rm -f {shlex.quote(board.path)}/{DEPLOYED_MARK}")    # the next deploy starts from HEAD~1
    return execute(plan, board, force=True, board_hashes={})


def main(argv: list[str] | None = None) -> int:
    from src.python.hosts import host
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--range", help="commits to deploy (default: from the last commit the board received)")
    ap.add_argument("--dry-run", action="store_true", help="show the plan; change nothing")
    ap.add_argument("--force", action="store_true", help="overwrite board-side edits")
    ap.add_argument("--rollback", action="store_true", help="undo the last deploy on the board")
    args = ap.parse_args(argv)

    board = Board(f"{host('PI_USER')}@{host('PI_HOST')}", host("REMOTE_PATH"), args.dry_run)
    units = read_units(PROJECT_ROOT)
    if args.rollback:
        return rollback(board, units, args.dry_run)

    rev_range = args.range or default_range(board)
    changed, deleted = changed_files(rev_range)
    head = git("rev-parse", "HEAD").strip()
    relevant = [p for p in changed if deployable(p) or p.startswith(DASHBOARD_ONLY)]
    if not relevant and not [p for p in deleted if deployable(p)]:
        print(f"deploy: nothing in {rev_range} runs on the board")
        if not args.dry_run and rev_range.endswith("..HEAD"):
            mark_deployed(board, head)
        return 0
    print(f"deploy: {rev_range}")
    old_rev, _, new_rev = rev_range.partition("..")
    copyable = [p for p in changed if deployable(p)]
    board_hashes, installed, active = board.state(copyable)
    plan = make_plan(changed, units, installed, active, deleted)
    show(plan)

    old = {p: git_blob_hash(old_rev, p) for p in copyable}
    new = {p: git_blob_hash(new_rev or "HEAD", p) for p in copyable}
    clash = conflicts(copyable, board_hashes, old, new)
    for path in list(clash):
        older = version_in_history(path, board_hashes[path])
        if older:
            print(f"  note:      {path} on the board is the older version from {older} - updating it")
            clash.remove(path)
    if clash and not args.force:
        print("\nREFUSED: these files on the board match no version the repo ever had -"
              "\nan edit made on the board. Compare, then re-run with --force:", file=sys.stderr)
        for path in clash:
            print(f"    {path}", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0
    result = 0 if plan.empty else execute(plan, board, args.force, board_hashes)
    if result == 0 and rev_range.endswith("..HEAD"):
        mark_deployed(board, head)
    return result


def mark_deployed(board: Board, commit: str) -> None:
    board.ssh(f"echo {commit} > {shlex.quote(board.path)}/{DEPLOYED_MARK}")


if __name__ == "__main__":
    raise SystemExit(main())
