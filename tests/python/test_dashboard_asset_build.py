"""The dashboard ships JavaScript old browsers can actually parse.

app.js is written with optional chaining and nullish coalescing. Those are
syntax, not APIs: a browser that does not understand them fails to parse the
whole file and runs none of it, so the dashboard sits on its "Loading…"
placeholders forever. No polyfill can rescue that, because a polyfill is
itself JavaScript that has to parse first. The deploy therefore ships a
compiled build, and these tests keep that guarantee honest.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-dashboard-assets.sh"
DEPLOY_SCRIPT = PROJECT_ROOT / "scripts" / "deploy-dashboard.sh"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

# Syntax the baseline browser (Safari 12.1 on iOS 12.5) cannot parse.
ES2020_SYNTAX = ("?.", "??")


def test_deploy_ships_the_compiled_bundle_not_the_source() -> None:
    deploy = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "build-dashboard-assets.sh" in deploy
    # Deploying web_static/ directly would put the untranspiled source on the
    # board and silently break every older browser again.
    assert 'rsync --checksum -av \\\n    "${STAGE_DIR}/"' in deploy
    assert '"${PROJECT_ROOT}/src/python/web_static/"' not in deploy


def test_build_script_declares_the_baseline_target() -> None:
    build = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert 'ES_TARGET="es2019"' in build
    # The target is a product decision, so it must carry its reason.
    assert "Safari 12.1" in build
    assert "iOS 12.5" in build


def test_source_still_uses_modern_syntax() -> None:
    """Guards the premise: without this, the other tests could pass vacuously."""
    source = APP_JS.read_text(encoding="utf-8")

    assert any(token in source for token in ES2020_SYNTAX), (
        "app.js no longer uses modern syntax, so the build step may be unnecessary"
    )


@pytest.mark.skipif(shutil.which("npx") is None, reason="needs Node.js to run esbuild")
def test_compiled_bundle_is_parseable_by_the_baseline_browser(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), str(tmp_path / "stage")],
        capture_output=True, text=True, timeout=300,
    )

    assert result.returncode == 0, f"build failed:\n{result.stdout}\n{result.stderr}"

    built = (tmp_path / "stage" / "app.js").read_text(encoding="utf-8")
    for token in ES2020_SYNTAX:
        assert token not in built, f"compiled bundle still contains {token!r}"

    # Everything else in web_static has to come along, not just app.js.
    for name in ("index.html", "styles.css", "login.html", "app.js.map"):
        assert (tmp_path / "stage" / name).exists(), f"{name} missing from the staged build"


@pytest.mark.skipif(shutil.which("npx") is None, reason="needs Node.js to run esbuild")
def test_compiled_bundle_is_not_larger_than_the_source(tmp_path: Path) -> None:
    subprocess.run(
        ["bash", str(BUILD_SCRIPT), str(tmp_path / "stage")],
        capture_output=True, text=True, timeout=300, check=True,
    )

    # Compiling drops comments, so supporting old browsers costs modern ones
    # nothing. If this ever flips, the trade-off deserves a fresh look.
    assert (tmp_path / "stage" / "app.js").stat().st_size <= APP_JS.stat().st_size
