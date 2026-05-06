"""API: Chat with project ID"""
from __future__ import annotations
import json
from fastapi import APIRouter, Path as FPath
from pydantic import BaseModel
from app.services.llm_client import call_llm
from app.db.connection import get_connection

router = APIRouter(prefix="/api/projects/{project_id}/chat", tags=["chat"])

SYSTEM_PROMPT = """You are ChaseBase procurement assistant. Answer in Chinese.
Available tools (respond as JSON {"tool": "...", "args": {...}} when needed):
- search_materials(po_number, supplier, status, overdue_only, limit)
- get_material(po_number, item_no)
- query_overview()
Otherwise answer directly in Chinese."""


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.post("")
def chat(req: ChatRequest, project_id: str = FPath(...)):
    history_text = "\n".join(
        f"[{m['role']}]: {m['content']}" for m in req.history[-8:]
    )
    user_content = (history_text + "\n" if history_text else "") + "[user]: " + req.message

    try:
        raw = call_llm(SYSTEM_PROMPT, user_content, max_tokens=1200)
    except RuntimeError as e:
        return {"answer": f"LLM 配置错误：{e}", "tool_called": None, "tool_result": None}

    try:
        parsed = json.loads(raw.strip())
        if "tool" in parsed and "args" in parsed:
            tool_result = _call_tool(parsed["tool"], parsed["args"], project_id)
            try:
                summary = call_llm(
                    "You are a procurement assistant. Summarize tool results in concise Chinese.",
                    "Tool: " + parsed["tool"] + "\nResult: " + json.dumps(tool_result, ensure_ascii=False),
                    max_tokens=400,
                )
            except RuntimeError:
                summary = json.dumps(tool_result, ensure_ascii=False)[:500]
            return {
                "answer": summary,
                "tool_called": parsed["tool"],
                "tool_result": tool_result,
            }
    except (json.JSONDecodeError, KeyError):
        pass

    return {"answer": raw, "tool_called": None, "tool_result": None}


def _call_tool(name: str, args: dict, project_id: str):
    conn = get_connection(project_id)
    try:
        if name == "search_materials":
            conditions, params = [], []
            if args.get("po_number"):
                conditions.append("po_number LIKE ?")
                params.append(f"%{args['po_number']}%")
            if args.get("supplier"):
                conditions.append("supplier LIKE ?")
                params.append(f"%{args['supplier']}%")
            if args.get("status"):
                conditions.append("status = ?")
                params.append(args["status"])
            if args.get("overdue_only"):
                conditions.append("current_eta < date('now') AND status='open'")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            limit = int(args.get("limit", 20))
            rows = conn.execute(
                f"SELECT po_number, item_no, description, supplier, current_eta, status "
                f"FROM materials {where} LIMIT ?",
                params + [limit],
            ).fetchall()
            return [dict(r) for r in rows]

        elif name == "get_material":
            row = conn.execute(
                "SELECT * FROM materials WHERE po_number=? AND item_no=?",
                (args.get("po_number", ""), args.get("item_no", "")),
            ).fetchone()
            return dict(row) if row else {}

        elif name == "query_overview":
            total = conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
            open_ = conn.execute("SELECT COUNT(*) FROM materials WHERE status='open'").fetchone()[0]
            overdue = conn.execute(
                "SELECT COUNT(*) FROM materials WHERE status='open' AND current_eta < date('now')"
            ).fetchone()[0]
            no_eta = conn.execute(
                "SELECT COUNT(*) FROM materials WHERE status='open' AND (current_eta IS NULL OR current_eta='')"
            ).fetchone()[0]
            return {"total": total, "open": open_, "overdue": overdue, "no_eta": no_eta}

        else:
            return {"error": f"unknown tool: {name}"}
    finally:
        conn.close()
