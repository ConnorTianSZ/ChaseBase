"""API: Materials CRUD with project ID"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path
from app.db.connection import get_connection
from app.models.material import MaterialUpdate
from app.update_policy import bulk_update_fields, try_update_field

router = APIRouter(prefix="/api/projects/{project_id}/materials", tags=["materials"])


@router.get("")
def list_materials(
    project_id:  str            = Path(...),
    po_number:   Optional[str]  = Query(None),
    buyer_email: Optional[str]  = Query(None),
    supplier:    Optional[str]  = Query(None),
    status:      Optional[str]  = Query(None),
    station_no:  Optional[str]  = Query(None),
    purchasing_group: Optional[str] = Query(None),
    is_focus:    Optional[bool] = Query(None),
    overdue:     bool           = Query(False),
    no_eta:      bool           = Query(False),
    search:      Optional[str]  = Query(None),
    page:        int            = Query(1, ge=1),
    page_size:   int            = Query(50, ge=1, le=500),
):
    conditions, params = [], []

    if po_number:
        conditions.append("po_number LIKE ?")
        params.append(f"%{po_number}%")
    if buyer_email:
        conditions.append("buyer_email = ?")
        params.append(buyer_email)
    if supplier:
        conditions.append("supplier LIKE ?")
        params.append(f"%{supplier}%")
    if status:
        conditions.append("status = ?")
        params.append(status)
    if station_no:
        conditions.append("station_no = ?")
        params.append(station_no)
    if purchasing_group:
        conditions.append("purchasing_group = ?")
        params.append(purchasing_group.upper())
    if is_focus is not None:
        conditions.append("is_focus = ?")
        params.append(1 if is_focus else 0)
    if overdue:
        conditions.append("current_eta < date('now') AND status = 'open'")
    if no_eta:
        conditions.append("(current_eta IS NULL OR current_eta = '') AND status = 'open'")
    if search:
        conditions.append(
            "(po_number LIKE ? OR part_no LIKE ? OR description LIKE ? OR supplier LIKE ?)"
        )
        like = f"%{search}%"
        params += [like, like, like, like]

    where  = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    conn = get_connection(project_id)
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM materials {where}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT * FROM materials {where} "
            f"ORDER BY current_eta ASC NULLS LAST LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/filter_options")
def filter_options(project_id: str = Path(...)):
    conn = get_connection(project_id)
    try:
        stations  = [r[0] for r in conn.execute(
            "SELECT DISTINCT station_no FROM materials WHERE station_no IS NOT NULL ORDER BY station_no"
        ).fetchall()]
        pgs = [r[0] for r in conn.execute(
            "SELECT DISTINCT purchasing_group FROM materials WHERE purchasing_group IS NOT NULL ORDER BY purchasing_group"
        ).fetchall()]
        suppliers = [r[0] for r in conn.execute(
            "SELECT DISTINCT supplier FROM materials WHERE supplier IS NOT NULL ORDER BY supplier"
        ).fetchall()]
        return {"stations": stations, "purchasing_groups": pgs, "suppliers": suppliers}
    finally:
        conn.close()


@router.get("/{material_id}")
def get_material(project_id: str = Path(...), material_id: int = Path(...)):
    conn = get_connection(project_id)
    try:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        return dict(row)
    finally:
        conn.close()


@router.patch("/{material_id}")
def update_material(
    material_id: int,
    body: MaterialUpdate,
    project_id: str = Path(...),
    source: str = "chat_command",
):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        return {"ok": True, "updated": 0}
    conn = get_connection(project_id)
    try:
        results = bulk_update_fields(conn, material_id, updates, source=source)
        conn.commit()
        return {"ok": True, "results": {k: {"ok": ok, "reason": r} for k, (ok, r) in results.items()}}
    finally:
        conn.close()


@router.delete("/{material_id}")
def delete_material(project_id: str = Path(...), material_id: int = Path(...)):
    conn = get_connection(project_id)
    try:
        conn.execute("DELETE FROM materials WHERE id=?", (material_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/{material_id}/history")
def material_history(project_id: str = Path(...), material_id: int = Path(...)):
    """获取单行物料的所有字段更新历史"""
    conn = get_connection(project_id)
    try:
        rows = conn.execute(
            "SELECT * FROM field_updates WHERE material_id=? ORDER BY timestamp DESC LIMIT 50",
            (material_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/{material_id}/toggle_focus")
def toggle_focus(project_id: str = Path(...), material_id: int = Path(...)):
    """切换 is_focus 标记"""
    conn = get_connection(project_id)
    try:
        row = conn.execute("SELECT is_focus FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(404, "Material not found")
        new_val = 0 if row["is_focus"] else 1
        conn.execute("UPDATE materials SET is_focus=? WHERE id=?", (new_val, material_id))
        conn.commit()
        return {"ok": True, "is_focus": bool(new_val)}
    finally:
        conn.close()
