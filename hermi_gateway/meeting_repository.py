from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .meeting_modes import HOST_ROLES


def room_by_id(conn, room_id: str) -> dict[str, Any]:
    row = conn.execute("select * from rooms where room_id = ?", (room_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="room_not_found")
    return dict(row)


def room_members(conn, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select rm.role as member_role, rm.joined_at as member_joined_at, a.*
        from room_members rm join agents a on a.agent_id = rm.agent_id
        where rm.room_id = ? order by rm.joined_at asc
        """,
        (room_id,),
    ).fetchall()
    return sorted(
        [dict(row) for row in rows],
        key=lambda item: (
            0 if item["member_role"] in HOST_ROLES else 1,
            float(item.get("member_joined_at") or 0),
        ),
    )


def room_runs(conn, room_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            "select * from workflow_runs where room_id = ? order by created_at desc", (room_id,)
        ).fetchall()
    ]
