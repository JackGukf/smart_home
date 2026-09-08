"""The dashboard's side of "the LLM authors, rules execute".

The model cannot be tested and is not tested here. What is tested is everything
that stands between the model and the house: that a proposal is inert until
somebody installs it, that a proposal name out of a URL cannot address a file
this code did not write, and that two drafts of the same request do not
silently overwrite each other.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.python.automation_author import Draft
from src.python.web_app import (
    _automation_from_proposal,
    _proposal_path,
    _read_proposals,
    _write_proposal,
    create_app,
)

AUTOMATION = {
    "alias": "Office switch off at 11pm",
    "triggers": [{"trigger": "time", "at": "23:00:00"}],
    "actions": [{"action": "switch.turn_off", "entity_id": "switch.office_switch"}],
}


def make_draft(**overrides) -> Draft:
    fields = {
        "request": "turn off the office switch every night at 11pm",
        "automation": AUTOMATION,
        "yaml_text": "- alias: Office switch off at 11pm\n",
        "problems": [],
        "hints": [],
        "attempts": 1,
        "elapsed": 9.4,
        "entities_shown": 25,
    }
    fields.update(overrides)
    return Draft(**fields)


def test_a_proposal_name_cannot_escape_the_proposals_directory(tmp_path) -> None:
    """The name comes out of the URL, so this is the only thing guarding the path."""
    for hostile in ("../../.env", "..%2F.env", "/etc/passwd", "notes.txt", ".env"):
        with pytest.raises(HTTPException) as raised:
            _proposal_path(tmp_path, hostile)
        assert raised.value.status_code == 400


def test_a_second_draft_of_the_same_request_does_not_overwrite_the_first(tmp_path) -> None:
    """Asking twice usually means you want to compare, not replace."""
    first = _write_proposal(tmp_path, make_draft())
    second = _write_proposal(tmp_path, make_draft())

    assert first == "office-switch-off-at-11pm.yaml"
    assert second == "office-switch-off-at-11pm-2.yaml"
    assert (tmp_path / first).is_file() and (tmp_path / second).is_file()


def test_a_proposal_carries_the_request_and_the_review_hints(tmp_path) -> None:
    """The hints are the whole reason a human is in the loop, so they must survive
    the round trip to disk and back."""
    name = _write_proposal(tmp_path, make_draft(
        hints=["the request mentions 5 minutes but nothing turns it off again"]))

    (proposal,) = _read_proposals(tmp_path)

    assert proposal["name"] == name
    assert proposal["alias"] == "Office switch off at 11pm"
    assert proposal["request"] == "turn off the office switch every night at 11pm"
    assert proposal["hints"] == [
        "the request mentions 5 minutes but nothing turns it off again"]


def test_reading_an_empty_directory_is_not_an_error(tmp_path) -> None:
    assert _read_proposals(tmp_path / "not-created-yet") == []


def test_a_file_that_is_not_an_automation_is_refused_at_install(tmp_path) -> None:
    path = tmp_path / "junk.yaml"
    path.write_text("just: a mapping\n", encoding="utf-8")

    with pytest.raises(HTTPException) as raised:
        _automation_from_proposal(path)
    assert raised.value.status_code == 400


def test_listing_proposals_needs_no_home_assistant(tmp_path) -> None:
    """The dashboard must still render its automation view with the LLM or Home
    Assistant down - the proposals are just files."""
    _write_proposal(tmp_path, make_draft())
    client = TestClient(create_app(check_camera_ports=False, proposals_path=tmp_path))

    response = client.get("/api/automations/proposals")

    assert response.status_code == 200
    assert [p["alias"] for p in response.json()["proposals"]] == \
        ["Office switch off at 11pm"]


def test_deleting_a_proposal_that_is_not_there_is_a_404(tmp_path) -> None:
    client = TestClient(create_app(check_camera_ports=False, proposals_path=tmp_path))

    assert client.delete("/api/automations/proposals/nothing-here.yaml").status_code == 404


def test_an_empty_request_is_refused_before_the_model_is_woken(tmp_path) -> None:
    """Waking a 4B model costs seconds; refusing an empty string costs nothing."""
    client = TestClient(create_app(check_camera_ports=False, proposals_path=tmp_path))

    response = client.post("/api/automations/draft", json={"request": "   "})

    assert response.status_code == 400
