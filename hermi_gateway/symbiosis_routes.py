from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field


class EvolutionNoteBody(BaseModel):
    content: str = Field(max_length=12000)


class EvolutionNotePinBody(BaseModel):
    pinned: bool


class FeatureProposalBody(BaseModel):
    title: str = Field(default="", max_length=140)
    content: str = Field(default="", max_length=4000)
    proposal_type: Literal["support", "poll"] = "support"
    options: list[str] = Field(default_factory=list, max_length=8)


class FeatureVoteBody(BaseModel):
    choice: str = Field(min_length=1, max_length=140)


class FeatureCommentBody(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def register_symbiosis_routes(
    app: FastAPI,
    *,
    conn: sqlite3.Connection,
    current_user: Callable[..., dict[str, Any]],
    owner_user: Callable[..., dict[str, Any]],
    audit: Callable[[sqlite3.Connection, str, str, dict[str, Any]], None],
) -> None:
    support_options = ["support", "neutral", "oppose"]

    def required_text(value: str, field: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail=f"{field}_required")
        return text

    def note_by_id(note_id: str) -> dict[str, Any]:
        row = conn.execute("select * from evolution_notes where note_id = ?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="evolution_note_not_found")
        return dict(row)

    def author_display_name(user_id: str) -> str:
        row = conn.execute("select display_name from users where user_id = ?", (user_id,)).fetchone()
        return str(row["display_name"] or user_id) if row else user_id

    def serialize_note(note: dict[str, Any]) -> dict[str, Any]:
        serialized = dict(note)
        serialized["author_display_name"] = author_display_name(str(note["created_by"]))
        serialized["is_pinned"] = bool(note.get("pinned_at"))
        return serialized

    def proposal_by_id(proposal_id: str) -> dict[str, Any]:
        row = conn.execute("select * from feature_proposals where proposal_id = ?", (proposal_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="feature_proposal_not_found")
        return dict(row)

    def proposal_kind(proposal: dict[str, Any]) -> str:
        return "poll" if proposal.get("proposal_type") == "poll" else "support"

    def is_owner(user: dict[str, Any]) -> bool:
        return user.get("role") == "owner" or bool(user.get("can_approve"))

    def viewer_revealed(proposal_id: str, user_id: str) -> bool:
        row = conn.execute(
            "select 1 from feature_proposal_opinion_reveals where proposal_id = ? and user_id = ?",
            (proposal_id, user_id),
        ).fetchone()
        return row is not None

    def viewer_vote_confirmed(proposal_id: str, user_id: str) -> bool:
        row = conn.execute(
            "select 1 from feature_proposal_vote_confirms where proposal_id = ? and user_id = ?",
            (proposal_id, user_id),
        ).fetchone()
        return row is not None

    def require_unlocked_participation(proposal_id: str, user: dict[str, Any]) -> None:
        if is_owner(user):
            return
        vote = conn.execute(
            "select 1 from feature_votes where proposal_id = ? and user_id = ?",
            (proposal_id, user["user_id"]),
        ).fetchone()
        if not vote:
            raise HTTPException(status_code=409, detail="proposal_participation_required")
        if viewer_revealed(proposal_id, user["user_id"]):
            raise HTTPException(status_code=409, detail="proposal_participation_locked")

    def proposal_options(proposal: dict[str, Any]) -> list[str]:
        if proposal_kind(proposal) == "support":
            return support_options
        try:
            options = json.loads(str(proposal.get("options_json") or "[]"))
        except json.JSONDecodeError:
            options = []
        return [str(option) for option in options if str(option).strip()]

    def normalize_poll_options(values: list[str]) -> list[str]:
        options = [str(value or "").strip() for value in values]
        options = [option for option in options if option]
        if len(options) < 2:
            raise HTTPException(status_code=422, detail="poll_options_minimum_two")
        if len(set(options)) != len(options):
            raise HTTPException(status_code=422, detail="poll_options_must_be_unique")
        return options

    def serialize_proposal(proposal: dict[str, Any], viewer: dict[str, Any]) -> dict[str, Any]:
        viewer_user_id = str(viewer["user_id"])
        options = proposal_options(proposal)
        counts = {option: 0 for option in options}
        for vote in conn.execute(
            "select choice, count(*) as count from feature_votes where proposal_id = ? group by choice",
            (proposal["proposal_id"],),
        ).fetchall():
            choice = str(vote["choice"])
            if choice in counts:
                counts[choice] = int(vote["count"])
        viewer_vote = conn.execute(
            "select choice from feature_votes where proposal_id = ? and user_id = ?",
            (proposal["proposal_id"], viewer_user_id),
        ).fetchone()
        viewer_comment = conn.execute(
            "select content from feature_proposal_comments where proposal_id = ? and user_id = ?",
            (proposal["proposal_id"], viewer_user_id),
        ).fetchone()
        revealed = viewer_revealed(proposal["proposal_id"], viewer_user_id)
        vote_confirmed = viewer_vote_confirmed(proposal["proposal_id"], viewer_user_id)
        can_view_vote_summary = bool(is_owner(viewer) or vote_confirmed)
        serialized = dict(proposal)
        serialized.pop("options_json", None)
        serialized["proposal_type"] = proposal_kind(proposal)
        serialized["options"] = options
        serialized["vote_summary"] = counts if can_view_vote_summary else {}
        serialized["viewer_vote"] = viewer_vote["choice"] if viewer_vote else ""
        serialized["viewer_vote_confirmed"] = vote_confirmed
        serialized["can_view_vote_summary"] = can_view_vote_summary
        serialized["viewer_comment"] = viewer_comment["content"] if viewer_comment else ""
        serialized["viewer_locked"] = bool(revealed and not is_owner(viewer))
        serialized["can_view_opinions"] = bool(is_owner(viewer) or revealed)
        serialized["author_display_name"] = author_display_name(str(proposal["created_by"]))
        return serialized

    @app.get("/symbiosis/notes")
    def list_evolution_notes(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = conn.execute(
            "select * from evolution_notes order by pinned_at is null asc, pinned_at desc, created_at desc"
        ).fetchall()
        return {"notes": [serialize_note(dict(row)) for row in rows]}

    @app.post("/symbiosis/notes")
    def create_evolution_note(body: EvolutionNoteBody, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:
        now = time.time()
        note = {
            "note_id": f"evo-{uuid.uuid4().hex}",
            "content": required_text(body.content, "content"),
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        conn.execute(
            "insert into evolution_notes (note_id, content, created_by, created_at, updated_at) values (?, ?, ?, ?, ?)",
            tuple(note.values()),
        )
        audit(conn, "evolution_note_created", user["user_id"], {"note_id": note["note_id"]})
        conn.commit()
        return {"note": serialize_note(note)}

    @app.patch("/symbiosis/notes/{note_id}")
    def update_evolution_note(
        note_id: str,
        body: EvolutionNoteBody,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        note_by_id(note_id)
        now = time.time()
        content = required_text(body.content, "content")
        conn.execute("update evolution_notes set content = ?, updated_at = ? where note_id = ?", (content, now, note_id))
        audit(conn, "evolution_note_updated", user["user_id"], {"note_id": note_id})
        conn.commit()
        return {"note": serialize_note(note_by_id(note_id))}

    @app.put("/symbiosis/notes/{note_id}/pin")
    def pin_evolution_note(
        note_id: str,
        body: EvolutionNotePinBody,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        note_by_id(note_id)
        pinned_at = time.time() if body.pinned else None
        conn.execute("update evolution_notes set pinned_at = ? where note_id = ?", (pinned_at, note_id))
        audit(conn, "evolution_note_pin_changed", user["user_id"], {"note_id": note_id, "pinned": body.pinned})
        conn.commit()
        return {"note": serialize_note(note_by_id(note_id))}

    @app.delete("/symbiosis/notes/{note_id}")
    def delete_evolution_note(note_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:
        note_by_id(note_id)
        conn.execute("delete from evolution_notes where note_id = ?", (note_id,))
        audit(conn, "evolution_note_deleted", user["user_id"], {"note_id": note_id})
        conn.commit()
        return {"deleted": True}

    def blueprint_by_id(note_id: str) -> dict[str, Any]:
        row = conn.execute("select * from evolution_blueprints where note_id = ?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="evolution_blueprint_not_found")
        return dict(row)

    @app.get("/symbiosis/blueprints")
    def list_evolution_blueprints(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = conn.execute(
            "select * from evolution_blueprints order by pinned_at is null asc, pinned_at desc, created_at desc"
        ).fetchall()
        return {"blueprints": [serialize_note(dict(row)) for row in rows]}

    @app.post("/symbiosis/blueprints")
    def create_evolution_blueprint(body: EvolutionNoteBody, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:
        now = time.time()
        blueprint = {
            "note_id": f"blueprint-{uuid.uuid4().hex}",
            "content": required_text(body.content, "content"),
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        conn.execute(
            "insert into evolution_blueprints (note_id, content, created_by, created_at, updated_at) values (?, ?, ?, ?, ?)",
            tuple(blueprint.values()),
        )
        audit(conn, "evolution_blueprint_created", user["user_id"], {"note_id": blueprint["note_id"]})
        conn.commit()
        return {"blueprint": serialize_note(blueprint)}

    @app.patch("/symbiosis/blueprints/{note_id}")
    def update_evolution_blueprint(
        note_id: str,
        body: EvolutionNoteBody,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        blueprint_by_id(note_id)
        conn.execute(
            "update evolution_blueprints set content = ?, updated_at = ? where note_id = ?",
            (required_text(body.content, "content"), time.time(), note_id),
        )
        audit(conn, "evolution_blueprint_updated", user["user_id"], {"note_id": note_id})
        conn.commit()
        return {"blueprint": serialize_note(blueprint_by_id(note_id))}

    @app.put("/symbiosis/blueprints/{note_id}/pin")
    def pin_evolution_blueprint(
        note_id: str,
        body: EvolutionNotePinBody,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        blueprint_by_id(note_id)
        conn.execute(
            "update evolution_blueprints set pinned_at = ? where note_id = ?",
            (time.time() if body.pinned else None, note_id),
        )
        audit(conn, "evolution_blueprint_pin_changed", user["user_id"], {"note_id": note_id, "pinned": body.pinned})
        conn.commit()
        return {"blueprint": serialize_note(blueprint_by_id(note_id))}

    @app.delete("/symbiosis/blueprints/{note_id}")
    def delete_evolution_blueprint(note_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:
        blueprint_by_id(note_id)
        conn.execute("delete from evolution_blueprints where note_id = ?", (note_id,))
        audit(conn, "evolution_blueprint_deleted", user["user_id"], {"note_id": note_id})
        conn.commit()
        return {"deleted": True}

    @app.get("/symbiosis/proposals")
    def list_feature_proposals(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = conn.execute("select * from feature_proposals order by created_at desc").fetchall()
        return {"proposals": [serialize_proposal(dict(row), user) for row in rows]}

    @app.post("/symbiosis/proposals")
    def create_feature_proposal(body: FeatureProposalBody, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:
        now = time.time()
        if body.proposal_type == "poll":
            title = required_text(body.title, "title")
            content = str(body.content or "").strip()
            options = normalize_poll_options(body.options)
        else:
            title = required_text(body.title, "title")
            content = required_text(body.content, "content")
            options = support_options
        proposal = {
            "proposal_id": f"proposal-{uuid.uuid4().hex}",
            "title": title,
            "content": content,
            "proposal_type": body.proposal_type,
            "options_json": json.dumps(options, ensure_ascii=False),
            "status": "open",
            "created_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
        }
        conn.execute(
            "insert into feature_proposals (proposal_id, title, content, proposal_type, options_json, status, created_by, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(proposal.values()),
        )
        audit(conn, "feature_proposal_created", user["user_id"], {"proposal_id": proposal["proposal_id"]})
        conn.commit()
        return {"proposal": serialize_proposal(proposal, user)}

    @app.post("/symbiosis/proposals/{proposal_id}/vote")
    def vote_feature_proposal(
        proposal_id: str,
        body: FeatureVoteBody,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal = proposal_by_id(proposal_id)
        if not is_owner(user) and (
            viewer_revealed(proposal_id, user["user_id"])
            or viewer_vote_confirmed(proposal_id, user["user_id"])
        ):
            raise HTTPException(status_code=409, detail="proposal_participation_locked")
        choice = body.choice.strip()
        if choice not in proposal_options(proposal):
            raise HTTPException(status_code=422, detail="invalid_vote_choice")
        now = time.time()
        conn.execute(
            "insert into feature_votes (proposal_id, user_id, choice, created_at, updated_at) values (?, ?, ?, ?, ?) "
            "on conflict(proposal_id, user_id) do update set choice = excluded.choice, updated_at = excluded.updated_at",
            (proposal_id, user["user_id"], choice, now, now),
        )
        audit(conn, "feature_proposal_voted", user["user_id"], {"proposal_id": proposal_id, "choice": choice})
        conn.commit()
        return {"proposal_id": proposal_id, "choice": choice}

    @app.delete("/symbiosis/proposals/{proposal_id}/vote")
    def delete_feature_vote(
        proposal_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        if not is_owner(user) and (
            viewer_revealed(proposal_id, user["user_id"])
            or viewer_vote_confirmed(proposal_id, user["user_id"])
        ):
            raise HTTPException(status_code=409, detail="proposal_participation_locked")
        cursor = conn.execute(
            "delete from feature_votes where proposal_id = ? and user_id = ?",
            (proposal_id, user["user_id"]),
        )
        if cursor.rowcount:
            audit(conn, "feature_proposal_vote_cancelled", user["user_id"], {"proposal_id": proposal_id})
        conn.commit()
        return {"proposal_id": proposal_id, "deleted": bool(cursor.rowcount)}

    @app.post("/symbiosis/proposals/{proposal_id}/confirm-vote")
    def confirm_feature_vote(
        proposal_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        if is_owner(user):
            return {"proposal_id": proposal_id, "confirmed": False, "locked": False}
        vote = conn.execute(
            "select 1 from feature_votes where proposal_id = ? and user_id = ?",
            (proposal_id, user["user_id"]),
        ).fetchone()
        if not vote:
            raise HTTPException(status_code=409, detail="proposal_participation_required")
        now = time.time()
        conn.execute(
            "insert or ignore into feature_proposal_vote_confirms (proposal_id, user_id, confirmed_at) values (?, ?, ?)",
            (proposal_id, user["user_id"], now),
        )
        audit(conn, "feature_proposal_vote_confirmed", user["user_id"], {"proposal_id": proposal_id})
        conn.commit()
        return {"proposal_id": proposal_id, "confirmed": True, "locked": True}

    @app.post("/symbiosis/proposals/{proposal_id}/comment")
    def comment_feature_proposal(
        proposal_id: str,
        body: FeatureCommentBody,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        require_unlocked_participation(proposal_id, user)
        now = time.time()
        content = required_text(body.content, "comment")
        conn.execute(
            "insert into feature_proposal_comments (proposal_id, user_id, content, created_at, updated_at) values (?, ?, ?, ?, ?) "
            "on conflict(proposal_id, user_id) do update set content = excluded.content, updated_at = excluded.updated_at",
            (proposal_id, user["user_id"], content, now, now),
        )
        audit(conn, "feature_proposal_commented", user["user_id"], {"proposal_id": proposal_id})
        conn.commit()
        return {"proposal_id": proposal_id, "content": content}

    @app.delete("/symbiosis/proposals/{proposal_id}/comment")
    def delete_feature_proposal_comment(
        proposal_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        require_unlocked_participation(proposal_id, user)
        cursor = conn.execute(
            "delete from feature_proposal_comments where proposal_id = ? and user_id = ?",
            (proposal_id, user["user_id"]),
        )
        if cursor.rowcount:
            audit(conn, "feature_proposal_comment_deleted", user["user_id"], {"proposal_id": proposal_id})
        conn.commit()
        return {"proposal_id": proposal_id, "deleted": bool(cursor.rowcount)}

    @app.post("/symbiosis/proposals/{proposal_id}/reveal-opinions")
    def reveal_feature_proposal_opinions(
        proposal_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        if not is_owner(user):
            vote = conn.execute(
                "select 1 from feature_votes where proposal_id = ? and user_id = ?",
                (proposal_id, user["user_id"]),
            ).fetchone()
            if not vote:
                raise HTTPException(status_code=409, detail="proposal_participation_required")
            now = time.time()
            conn.execute(
                "insert or ignore into feature_proposal_opinion_reveals (proposal_id, user_id, revealed_at) values (?, ?, ?)",
                (proposal_id, user["user_id"], now),
            )
            audit(conn, "feature_proposal_opinions_revealed", user["user_id"], {"proposal_id": proposal_id})
            conn.commit()
        return {"proposal_id": proposal_id, "locked": not is_owner(user)}

    @app.get("/symbiosis/proposals/{proposal_id}/opinions")
    def list_feature_proposal_opinions(
        proposal_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        if not is_owner(user) and not viewer_revealed(proposal_id, user["user_id"]):
            raise HTTPException(status_code=403, detail="proposal_opinions_locked")
        rows = conn.execute(
            """
            select c.user_id, coalesce(u.display_name, c.user_id) as display_name,
                   c.content, c.created_at, c.updated_at, coalesce(v.choice, '') as choice
            from feature_proposal_comments c
            left join users u on u.user_id = c.user_id
            left join feature_votes v on v.proposal_id = c.proposal_id and v.user_id = c.user_id
            where c.proposal_id = ? order by c.updated_at asc
            """,
            (proposal_id,),
        ).fetchall()
        return {
            "proposal_id": proposal_id,
            "opinions": [
                {**dict(row), "comment": dict(row)["content"]}
                for row in rows
            ],
        }

    @app.delete("/symbiosis/proposals/{proposal_id}")
    def delete_feature_proposal(proposal_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:
        proposal_by_id(proposal_id)
        conn.execute("delete from feature_proposal_comments where proposal_id = ?", (proposal_id,))
        conn.execute("delete from feature_proposal_opinion_reveals where proposal_id = ?", (proposal_id,))
        conn.execute("delete from feature_proposal_vote_confirms where proposal_id = ?", (proposal_id,))
        conn.execute("delete from feature_votes where proposal_id = ?", (proposal_id,))
        conn.execute("delete from feature_proposals where proposal_id = ?", (proposal_id,))
        audit(conn, "feature_proposal_deleted", user["user_id"], {"proposal_id": proposal_id})
        conn.commit()
        return {"deleted": True}
