from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException

from . import admin_users
from .models import AdminUserCreate, AdminUserPatch, UserProfileFieldPatch


def register_admin_routes(
    app: FastAPI,
    *,
    conn: sqlite3.Connection,
    current_user: Callable[..., dict[str, Any]],
    owner_user: Callable[..., dict[str, Any]],
    require_perm: Callable[[str, dict[str, Any]], None],
    audit: Callable[[sqlite3.Connection, str, str, dict[str, Any]], None],
) -> None:
    @app.get("/admin/users")
    def list_users(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        require_perm("admin_users", user)
        return {"users": admin_users.list_users(conn)}

    @app.post("/admin/users")
    def create_user(
        body: AdminUserCreate,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        public, generated_token = admin_users.create_user(conn, body)
        audit(conn, "user_created", user["user_id"], {"user_id": body.user_id, "role": body.role})
        conn.commit()
        if generated_token:
            public["generated_token"] = generated_token
        return public

    @app.get("/admin/users/{user_id}")
    def user_detail(
        user_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        require_perm("admin_users", user)
        public = admin_users.get_user(conn, user_id)
        if public is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        return public

    @app.patch("/admin/users/{user_id}")
    def update_user(
        user_id: str,
        body: AdminUserPatch,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        values = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
        public = admin_users.update_user(conn, user_id, body)
        if public is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        audit(conn, "user_updated", user["user_id"], {"user_id": user_id, "fields": sorted(values)})
        conn.commit()
        return public

    @app.delete("/admin/users/{user_id}")
    def delete_user(
        user_id: str,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        try:
            deleted = admin_users.delete_user(conn, user_id, user["user_id"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if deleted is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        audit(conn, "user_deleted", user["user_id"], {"user_id": user_id})
        conn.commit()
        return {"deleted": True, "user": deleted}

    @app.get("/admin/users/{user_id}/profile")
    def get_user_profile(user_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        require_perm("admin_users", user)
        if admin_users.get_user(conn, user_id) is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        return admin_users.get_user_profile(conn, user_id)

    @app.put("/admin/users/{user_id}/profile/{field}")
    def update_user_profile(
        user_id: str,
        field: str,
        body: UserProfileFieldPatch,
        user: dict[str, Any] = Depends(owner_user),
    ) -> dict[str, Any]:
        if admin_users.get_user(conn, user_id) is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        try:
            profile = admin_users.update_user_profile_field(conn, user_id, field, body.value)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        audit(conn, "user_profile_updated", user["user_id"], {"user_id": user_id, "field": field})
        conn.commit()
        return profile
