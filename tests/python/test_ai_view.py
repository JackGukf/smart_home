"""The dashboard's AI view: the sidebar entry is a launcher, Automations lives
under it unchanged, and AI data takes bills and readings without importing them
on sight."""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import web_app

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "python" / "web_static"


def client(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    return TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False,
                                         ai_data_dir=tmp_path / "ai-data"))


def test_the_sidebar_entry_is_ai_and_opens_a_launcher():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    views = html[html.index('<div class="sidebar-section">Views</div>'):html.index('<div class="sidebar-section">System</div>')]

    assert 'data-view="ai"' in views and 'data-view="automations"' not in views
    launcher = html[html.index('data-view-panel="ai"'):html.index('data-view-panel="automations"')]
    for page in ("automations", "aidata"):
        assert f'class="app-tile" data-goto-view="{page}"' in launcher
        panel = html[html.index(f'data-view-panel="{page}"'):]
        assert 'class="page-back" data-goto-view="ai"' in panel[:panel.index("</div>") + 400]
    # The launcher stays lit while an app under it is open.
    assert 'automations: "ai", aidata: "ai"' in js
    # The proposal badge survived the rename.
    assert 'id="proposalCount"' in views


def test_automations_keeps_its_composer_and_proposals():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    panel = html[html.index('data-view-panel="automations"'):html.index('data-view-panel="aidata"')]
    assert 'id="automationRequest"' in panel and 'id="automationDraftBtn"' in panel
    assert 'id="automationProposals"' in panel


def test_the_ai_data_page_has_the_four_things_it_promises():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    panel = html[html.index('data-view-panel="aidata"'):html.index("<!-- ── ALARM VIEW ── -->")]
    assert 'id="aiFileInput"' in panel and "accept=\".pdf,.csv,.txt\"" in panel
    assert 'id="aiReadingValue"' in panel and 'id="aiInventory"' in panel
    assert 'id="aiFiles"' in panel and 'id="aiGasModel"' in panel
    assert "Nothing is uploaded anywhere" in panel


def test_upload_is_parsed_and_only_imported_when_asked(tmp_path):
    api = client(tmp_path)
    csv = b"Date,Usage (GJ)\n2026-01-31,8.42\n2026-02-28,7.10\n"

    doc = api.post("/api/ai-data/files", files={"file": ("usage.csv", csv, "text/csv")}).json()
    assert doc["file"]["status"] == "parsed" and doc["file"]["kind"] == "usage"
    assert api.get("/api/ai-data").json()["inventory"]["bills"]["count"] == 0   # parsed, not imported

    imported = api.post(f"/api/ai-data/files/{doc['file']['id']}/import").json()
    assert imported["added"] == 2
    assert api.get("/api/ai-data").json()["inventory"]["bills"]["count"] == 2


def test_the_same_file_twice_is_refused_and_rubbish_is_rejected(tmp_path):
    api = client(tmp_path)
    csv = b"Date,Usage (GJ)\n2026-01-31,8.42\n2026-02-28,7.10\n"
    assert api.post("/api/ai-data/files", files={"file": ("a.csv", csv, "text/csv")}).status_code == 200
    assert api.post("/api/ai-data/files", files={"file": ("b.csv", csv, "text/csv")}).status_code == 409
    assert api.post("/api/ai-data/files", files={"file": ("photo.jpg", b"\xff\xd8", "image/jpeg")}).status_code == 400
    assert api.post("/api/ai-data/files/999/import").status_code == 404


def test_readings_go_in_and_come_back_as_measured_stretches(tmp_path):
    api = client(tmp_path)
    assert api.post("/api/ai-data/readings", json={"at": "2026-09-18T20:00:00", "cubic_feet": 4100}).status_code == 200
    assert api.post("/api/ai-data/readings", json={"at": "2026-09-19T20:00:00", "cubic_feet": 4118}).status_code == 200

    doc = api.get("/api/ai-data").json()
    assert doc["inventory"]["readings"]["count"] == 2
    assert doc["inventory"]["readings"]["intervals"] == 1
    assert doc["readings"][0]["cubic_feet"] == 4118

    assert api.post("/api/ai-data/readings", json={"cubic_feet": -5}).status_code == 422
    assert api.post("/api/ai-data/readings", json={"at": "not a time", "cubic_feet": 5}).status_code == 400


def test_the_gas_model_says_what_it_is_waiting_for(tmp_path):
    doc = client(tmp_path).get("/api/ai-data").json()
    assert doc["gas"]["model"]["status"] == "not_enough_data"
    assert doc["gas"]["model"]["base_gj_per_day"] is None       # nothing invented
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "waiting for heating season" in js and "not enough data yet" in js
