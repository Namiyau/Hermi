from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
    )
    return TestClient(create_app(config))


def test_owner_manages_evolution_notes_while_friend_can_only_read(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    created_user = client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:reader", "display_name": "Reader", "token": "reader-token"},
    )
    assert created_user.status_code == 200
    friend_headers = {"Authorization": "Bearer reader-token"}

    created = client.post(
        "/symbiosis/notes",
        headers=owner_headers,
        json={"content": "# 演化纪要\n\n第一条记录"},
    )
    assert created.status_code == 200
    note = created.json()["note"]

    readable = client.get("/symbiosis/notes", headers=friend_headers)
    assert readable.status_code == 200
    assert readable.json()["notes"][0]["content"] == "# 演化纪要\n\n第一条记录"
    assert client.post("/symbiosis/notes", headers=friend_headers, json={"content": "越权"}).status_code == 403

    updated = client.patch(
        f"/symbiosis/notes/{note['note_id']}",
        headers=owner_headers,
        json={"content": "# 修订后的纪要"},
    )
    assert updated.status_code == 200
    assert updated.json()["note"]["content"] == "# 修订后的纪要"
    assert client.delete(f"/symbiosis/notes/{note['note_id']}", headers=owner_headers).status_code == 200


def test_owner_manages_evolution_blueprints_separately_from_notes(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    friend = client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:blueprint-reader", "display_name": "Blueprint reader", "token": "blueprint-token"},
    )
    assert friend.status_code == 200
    created = client.post(
        "/symbiosis/blueprints",
        headers=owner_headers,
        json={"content": "# 远期计划\n\n先做稳定性。"},
    )
    assert created.status_code == 200
    blueprint = created.json()["blueprint"]
    assert client.get("/symbiosis/notes", headers=owner_headers).json()["notes"] == []
    assert client.put(
        f"/symbiosis/blueprints/{blueprint['note_id']}/pin",
        headers=owner_headers,
        json={"pinned": True},
    ).json()["blueprint"]["is_pinned"] is True
    readable = client.get("/symbiosis/blueprints", headers={"Authorization": "Bearer blueprint-token"})
    assert readable.status_code == 200
    assert readable.json()["blueprints"][0]["content"].startswith("# 远期计划")


def test_owner_publishes_proposals_and_each_user_has_one_vote(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:voter", "display_name": "Voter", "token": "voter-token"},
    )
    friend_headers = {"Authorization": "Bearer voter-token"}

    created = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={"title": "加入夜间模式", "content": "为观测站增加低光界面。"},
    )
    assert created.status_code == 200
    proposal_id = created.json()["proposal"]["proposal_id"]

    vote = client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "support"},
    )
    assert vote.status_code == 200
    listing = client.get("/symbiosis/proposals", headers=friend_headers)
    proposal = listing.json()["proposals"][0]
    assert proposal["vote_summary"] == {}
    assert proposal["viewer_vote"] == "support"
    assert proposal["viewer_vote_confirmed"] is False
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/confirm-vote",
        headers=friend_headers,
    ).status_code == 200
    confirmed = client.get("/symbiosis/proposals", headers=friend_headers).json()["proposals"][0]
    assert confirmed["vote_summary"] == {"support": 1, "neutral": 0, "oppose": 0}
    assert confirmed["viewer_vote_confirmed"] is True
    assert client.delete(f"/symbiosis/proposals/{proposal_id}", headers=owner_headers).status_code == 200


def test_notes_and_proposals_expose_author_and_vote_can_be_cancelled(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:undo-vote", "display_name": "Undo voter", "token": "undo-vote-token"},
    )
    friend_headers = {"Authorization": "Bearer undo-vote-token"}

    note = client.post("/symbiosis/notes", headers=owner_headers, json={"content": "Author test."})
    assert note.status_code == 200
    assert note.json()["note"]["author_display_name"] == "Owner"

    created = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={"title": "Undo vote", "content": "A vote may be withdrawn before reveal."},
    )
    assert created.status_code == 200
    proposal = created.json()["proposal"]
    assert proposal["author_display_name"] == "Owner"
    proposal_id = proposal["proposal_id"]

    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "support"},
    ).status_code == 200
    assert client.delete(f"/symbiosis/proposals/{proposal_id}/vote", headers=friend_headers).status_code == 200
    listing = client.get("/symbiosis/proposals", headers=friend_headers).json()["proposals"]
    assert listing[0]["viewer_vote"] == ""
    assert listing[0]["vote_summary"] == {}


def test_owner_can_pin_evolution_note_and_everyone_sees_pins_first(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:pin-reader", "display_name": "Pin reader", "token": "pin-reader-token"},
    )
    first = client.post("/symbiosis/notes", headers=owner_headers, json={"content": "First note."}).json()["note"]
    second = client.post("/symbiosis/notes", headers=owner_headers, json={"content": "Second note."}).json()["note"]

    pinned = client.put(
        f"/symbiosis/notes/{first['note_id']}/pin",
        headers=owner_headers,
        json={"pinned": True},
    )

    assert pinned.status_code == 200
    assert pinned.json()["note"]["is_pinned"] is True
    notes = client.get("/symbiosis/notes", headers={"Authorization": "Bearer pin-reader-token"}).json()["notes"]
    assert [note["note_id"] for note in notes] == [first["note_id"], second["note_id"]]
    assert client.put(
        f"/symbiosis/notes/{first['note_id']}/pin",
        headers={"Authorization": "Bearer pin-reader-token"},
        json={"pinned": False},
    ).status_code == 403


def test_non_owner_opinion_reveal_locks_vote_and_comment(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:commenter", "display_name": "Commenter", "token": "commenter-token"},
    )
    friend_headers = {"Authorization": "Bearer commenter-token"}
    created = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={"title": "Comments", "content": "Discuss this feature."},
    )
    proposal_id = created.json()["proposal"]["proposal_id"]

    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "support"},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/comment",
        headers=friend_headers,
        json={"content": "I support it."},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/reveal-opinions",
        headers=friend_headers,
    ).status_code == 200

    opinions = client.get(f"/symbiosis/proposals/{proposal_id}/opinions", headers=friend_headers)
    assert opinions.status_code == 200
    assert opinions.json()["opinions"][0]["comment"] == "I support it."
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "oppose"},
    ).status_code == 409
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/comment",
        headers=friend_headers,
        json={"content": "I changed my mind."},
    ).status_code == 409


def test_owner_can_view_and_change_opinion_after_reveal(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    created = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={"title": "Owner controls", "content": "Owner remains unrestricted."},
    )
    proposal_id = created.json()["proposal"]["proposal_id"]

    assert client.get(f"/symbiosis/proposals/{proposal_id}/opinions", headers=owner_headers).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=owner_headers,
        json={"choice": "support"},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/comment",
        headers=owner_headers,
        json={"content": "First owner view."},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/reveal-opinions",
        headers=owner_headers,
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=owner_headers,
        json={"choice": "oppose"},
    ).status_code == 200
    changed = client.post(
        f"/symbiosis/proposals/{proposal_id}/comment",
        headers=owner_headers,
        json={"content": "Updated owner view."},
    )
    assert changed.status_code == 200


def test_owner_creates_poll_proposal_with_custom_options_and_users_vote_once(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:poll", "display_name": "Poll voter", "token": "poll-token"},
    )
    friend_headers = {"Authorization": "Bearer poll-token"}

    created = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={
            "proposal_type": "poll",
            "title": "下一项优先做什么？",
            "options": ["完善权限提示", "继续拆分前端", "补充会议室"],
        },
    )
    assert created.status_code == 200
    proposal = created.json()["proposal"]
    assert proposal["proposal_type"] == "poll"
    assert proposal["options"] == ["完善权限提示", "继续拆分前端", "补充会议室"]
    assert proposal["vote_summary"] == {"完善权限提示": 0, "继续拆分前端": 0, "补充会议室": 0}

    proposal_id = proposal["proposal_id"]
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "不存在的选项"},
    ).status_code == 422
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "完善权限提示"},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "继续拆分前端"},
    ).status_code == 200

    listed = client.get("/symbiosis/proposals", headers=friend_headers).json()["proposals"][0]
    assert listed["viewer_vote"] == "继续拆分前端"
    assert listed["vote_summary"] == {}
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/confirm-vote",
        headers=friend_headers,
    ).status_code == 200
    listed = client.get("/symbiosis/proposals", headers=friend_headers).json()["proposals"][0]
    assert listed["vote_summary"] == {"完善权限提示": 0, "继续拆分前端": 1, "补充会议室": 0}


def test_confirming_vote_locks_a_friend_choice_but_owner_stays_unlocked(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:confirmed", "display_name": "Confirmed", "token": "confirmed-token"},
    )
    friend_headers = {"Authorization": "Bearer confirmed-token"}
    proposal = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={"title": "Confirm vote", "content": "Selection must be confirmed."},
    ).json()["proposal"]
    proposal_id = proposal["proposal_id"]

    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "support"},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "oppose"},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/confirm-vote",
        headers=friend_headers,
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "support"},
    ).status_code == 409
    assert client.delete(f"/symbiosis/proposals/{proposal_id}/vote", headers=friend_headers).status_code == 409
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=owner_headers,
        json={"choice": "support"},
    ).status_code == 200


def test_participant_can_delete_own_comment_before_revealing_opinions(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:comment-delete", "display_name": "Comment delete", "token": "comment-delete-token"},
    )
    friend_headers = {"Authorization": "Bearer comment-delete-token"}
    proposal_id = client.post(
        "/symbiosis/proposals",
        headers=owner_headers,
        json={"title": "Delete comment", "content": "Comments remain editable before reveal."},
    ).json()["proposal"]["proposal_id"]

    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/vote",
        headers=friend_headers,
        json={"choice": "support"},
    ).status_code == 200
    assert client.post(
        f"/symbiosis/proposals/{proposal_id}/comment",
        headers=friend_headers,
        json={"content": "A temporary opinion."},
    ).status_code == 200
    assert client.delete(f"/symbiosis/proposals/{proposal_id}/comment", headers=friend_headers).json() == {
        "proposal_id": proposal_id,
        "deleted": True,
    }
    listed = client.get("/symbiosis/proposals", headers=friend_headers).json()["proposals"][0]
    assert listed["viewer_comment"] == ""
