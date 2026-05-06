"""LLM Tool: parse inbound email and apply ETA updates"""
from __future__ import annotations
import json
from app.db.connection import get_connection
from app.services.llm_client import parse_email_for_eta
from app.update_policy import bulk_update_fields


def parse_inbound_email(email_id: int, project_id: str = "default") -> dict:
    conn = get_connection(project_id)
    try:
        row = conn.execute("SELECT * FROM inbound_emails WHERE id=?", (email_id,)).fetchone()
        if not row:
            return {"ok": False, "reason": "email not found"}

        extracted = parse_email_for_eta(row["subject"] or "", row["body"] or "")
        conn.execute(
            "UPDATE inbound_emails SET llm_extracted_json=?, status='pending_confirm' WHERE id=?",
            (json.dumps(extracted, ensure_ascii=False), email_id),
        )
        conn.commit()
        return {"ok": True, "email_id": email_id, "extracted": extracted}
    finally:
        conn.close()


def apply_inbound_decision(
    email_id:   int,
    decision:   str,
    edits:      dict | None = None,
    project_id: str = "default",
) -> dict:
    conn = get_connection(project_id)
    try:
        row = conn.execute("SELECT * FROM inbound_emails WHERE id=?", (email_id,)).fetchone()
        if not row:
            return {"ok": False, "reason": "email not found"}

        if decision == "apply":
            extracted: dict = json.loads(row["llm_extracted_json"] or "{}")
            if edits:
                extracted.update(edits)
            mat_id = row["matched_material_id"]
            if not mat_id:
                return {"ok": False, "reason": "no matched material; cannot apply update"}
            updates = {}
            if extracted.get("new_eta"):
                updates["supplier_eta"] = extracted["new_eta"]
                updates["current_eta"]  = extracted["new_eta"]
            if extracted.get("remarks"):
                updates["supplier_remarks"] = extracted["remarks"]
            results = bulk_update_fields(
                conn, mat_id, updates,
                source="email_reply",
                source_ref=row["outlook_entry_id"],
            )
            conn.execute(
                "UPDATE inbound_emails SET status='applied', operator_decision=? WHERE id=?",
                (decision, email_id),
            )
        elif decision == "ignore":
            conn.execute(
                "UPDATE inbound_emails SET status='ignored', operator_decision=? WHERE id=?",
                (decision, email_id),
            )
        elif decision == "manual":
            conn.execute(
                "UPDATE inbound_emails SET status='manual', operator_decision=? WHERE id=?",
                (decision, email_id),
            )
        else:
            return {"ok": False, "reason": f"unknown decision: {decision}"}

        conn.commit()
        return {"ok": True, "email_id": email_id, "decision": decision}
    finally:
        conn.close()
