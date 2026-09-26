"""scripts/deploy.py: what a commit copies, installs and restarts - and what it refuses."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("deploy_tool", ROOT / "scripts" / "deploy.py")
deploy = importlib.util.module_from_spec(spec)
sys.modules["deploy_tool"] = deploy
spec.loader.exec_module(deploy)


def _repo(tmp_path: Path) -> Path:
    py = tmp_path / "src" / "python"
    py.mkdir(parents=True)
    (py / "web_app.py").write_text("from src.python import energy\nimport src.python.shared\n")
    (py / "energy.py").write_text("def f():\n    from src.python.lazy import thing\n")
    (py / "lazy.py").write_text("")
    (py / "shared.py").write_text("")
    (py / "detector.py").write_text("from src.python.shared import x\n")
    (py / "beat.py").write_text("")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run-dashboard.sh").write_text("exec uvicorn src.python.web_app:app\n")
    (tmp_path / "scripts" / "run-detector.sh").write_text(
        "# needs scripts/install-ai-services.sh first\n"
        "echo 'Create it with scripts/install-ai-services.sh'\n"
        "exec python -m src.python.detector\n")
    (tmp_path / "scripts" / "install-ai-services.sh").write_text("")
    units = tmp_path / "deploy" / "systemd" / "user"
    units.mkdir(parents=True)
    (units / "smart-home-dashboard.service").write_text(
        "[Service]\nExecStart=/home/orangepi/smart_home_AI/scripts/run-dashboard.sh\n")
    (units / "detector.service").write_text("[Service]\nExecStart=/home/orangepi/smart_home_AI/scripts/run-detector.sh\n")
    (units / "beat.service").write_text("[Service]\nType=oneshot\nExecStart=/usr/bin/python3 -m src.python.beat\n")
    (units / "beat.timer").write_text("[Timer]\nOnUnitActiveSec=5min\n")
    (units / "cast.service").write_text("[Service]\nExecStart=/usr/bin/python3 -m src.python.shared\n")
    return tmp_path


INSTALLED = {"smart-home-dashboard.service", "detector.service", "beat.service", "beat.timer", "cast.service"}
ACTIVE = {"smart-home-dashboard.service", "detector.service", "beat.timer"}


def _plan(tmp_path, changed, active=ACTIVE, installed=INSTALLED, deleted=()):
    return deploy.make_plan(changed, deploy.read_units(_repo(tmp_path)), installed, active, list(deleted))


def test_imports_are_followed_including_lazy_ones(tmp_path):
    root = _repo(tmp_path)
    assert deploy.closure(root, {"web_app"}) == {
        "src/python/web_app.py", "src/python/energy.py", "src/python/lazy.py", "src/python/shared.py"}


def test_a_detector_change_restarts_the_detector_only(tmp_path):
    plan = _plan(tmp_path, ["src/python/detector.py"])
    assert plan.copy == ["src/python/detector.py"]
    assert plan.restart == ["detector.service"] and not plan.dashboard


def test_a_module_the_dashboard_imports_deploys_the_dashboard(tmp_path):
    plan = _plan(tmp_path, ["src/python/lazy.py"])
    assert plan.dashboard and DASHBOARD not in plan.restart


DASHBOARD = "smart-home-dashboard.service"


def test_a_shared_module_restarts_every_running_user_and_notes_the_stopped_one(tmp_path):
    plan = _plan(tmp_path, ["src/python/shared.py"])
    assert plan.dashboard and plan.restart == ["detector.service"]
    assert any("cast.service" in n and "not running" in n for n in plan.notes)


def test_a_timer_job_is_never_restarted(tmp_path):
    """A oneshot runs the new code on its next tick; restarting it would run it now."""
    plan = _plan(tmp_path, ["src/python/beat.py"])
    assert plan.copy == ["src/python/beat.py"] and plan.restart == [] and plan.install_units == []


def test_a_changed_unit_file_is_installed_only_where_it_is_installed(tmp_path):
    plan = _plan(tmp_path, ["deploy/systemd/user/beat.timer", "deploy/systemd/user/detector.service"],
                 installed=INSTALLED - {"detector.service"})
    assert plan.install_units == ["beat.timer"]
    assert "beat.timer" in plan.restart
    assert any("detector.service" in n and "not installed" in n for n in plan.notes)


def test_a_mention_in_a_message_is_not_a_dependency(tmp_path):
    assert _plan(tmp_path, ["scripts/install-ai-services.sh"]).restart == []


def test_dashboard_assets_go_through_the_dashboard_deploy_not_a_copy(tmp_path):
    plan = _plan(tmp_path, ["src/python/web_static/app.js", "tplink_switches.json"])
    assert plan.dashboard and plan.copy == []


def test_docs_and_tests_deploy_nothing(tmp_path):
    assert _plan(tmp_path, ["docs/x.md", "tests/python/test_x.py"]).empty


def test_requirements_install_and_deletions_are_noted(tmp_path):
    plan = _plan(tmp_path, ["src/python/requirements.txt"], deleted=["scripts/old.sh"])
    assert plan.pip
    assert any("scripts/old.sh" in n and "deleted" in n for n in plan.notes)


def test_a_board_side_edit_is_refused_but_old_or_new_is_fine():
    paths = ["a.py", "b.py", "c.py", "d.py"]
    board = {"a.py": "OLD", "b.py": "NEW", "c.py": "EDITED", "d.py": None}
    old = {"a.py": "OLD", "b.py": "OLD", "c.py": "OLD", "d.py": None}
    new = {"a.py": "NEW", "b.py": "NEW", "c.py": "NEW", "d.py": "NEW"}
    assert deploy.conflicts(paths, board, old, new) == ["c.py"]


def test_the_real_repo_detector_and_dashboard():
    units = deploy.read_units(ROOT)
    active = {"npu-detector.service", "smart-home-dashboard.service", "night-watch.service", "go2rtc.service"}
    plan = deploy.make_plan(["src/python/npu_detector.py"], units, set(units), active)
    assert plan.restart == ["npu-detector.service"] and not plan.dashboard
    plan = deploy.make_plan(["src/python/safety_sensors.py"], units, set(units), active)
    assert plan.dashboard and plan.restart == []
    plan = deploy.make_plan(["scripts/generate-go2rtc-config.py"], units, set(units), active)
    assert plan.restart == ["go2rtc.service"]


def test_the_dashboard_deploy_is_asked_not_to_restart_go2rtc():
    source = (ROOT / "scripts" / "deploy.py").read_text(encoding="utf-8")
    assert '"--skip-go2rtc"' in source
    dashboard = (ROOT / "scripts" / "deploy-dashboard.sh").read_text(encoding="utf-8")
    assert "--skip-go2rtc) RESTART_GO2RTC=0" in dashboard
