"""
LLM client wrapper — 支持 Anthropic / OpenAI / 自定义兼容端点
"""
from __future__ import annotations
import json
from app.config import get_settings


def _resolve_key():
    """按优先级返回 API key: api_key > anthropic_api_key > env fallback"""
    s = get_settings()
    return s.api_key or s.anthropic_api_key or ""


def call_llm(
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 1024,
    response_format: str = "text",
) -> str:
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").lower()
    model = model or settings.llm_model or ""

    if response_format == "json":
        system = system + "\nRespond in valid JSON only. No markdown."

    if provider == "anthropic":
        return _call_anthropic(system, user, model, max_tokens)

    # OpenAI 兼容（也覆盖大部分第三方代理）
    if provider in ("openai", "custom"):
        return _call_openai_compat(system, user, model, max_tokens)

    raise ValueError(f"Unsupported LLM provider: {provider}")


def _call_anthropic(system: str, user: str, model: str, max_tokens: int) -> str:
    import anthropic
    api_key = _resolve_key()
    if not api_key:
        raise RuntimeError("API key not configured. Set ANTHROPIC_API_KEY or API_KEY in Settings.")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model or "claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _call_openai_compat(system: str, user: str, model: str, max_tokens: int) -> str:
    """OpenAI 兼容格式，支持自定义 base_url（如 Azure、代理等）"""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "openai package not installed. Run: pip install openai"
        )
    settings = get_settings()
    api_key = _resolve_key()
    if not api_key:
        raise RuntimeError("API key not configured. Set API_KEY or ANTHROPIC_API_KEY in Settings.")

    kwargs = {"api_key": api_key}
    if settings.api_base:
        kwargs["base_url"] = settings.api_base

    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model or "gpt-4o",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def parse_email_for_eta(email_subject: str, email_body: str) -> dict:
    system = (
        "You are a procurement assistant. Extract delivery info from supplier emails. "
        "Return JSON: {new_eta, remarks, confidence, po_number, item_nos}. "
        "new_eta: YYYY-MM-DD or null. confidence: 0.0-1.0."
    )
    user = "Subject: " + email_subject + "\n\nBody:\n" + email_body[:3000]
    raw = call_llm(system, user, response_format="json")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"new_eta": None, "remarks": raw[:200], "confidence": 0.3, "po_number": None, "item_nos": []}


def generate_chase_email(materials: list, tone: str = "formal", template: str = "") -> str:
    lines = []
    for m in materials:
        lines.append(
            "  - PO %s line%s %s supplier:%s eta:%s" % (
                m.get("po_number", ""),
                m.get("item_no", ""),
                m.get("part_no", ""),
                m.get("supplier", ""),
                m.get("current_eta", ""),
            )
        )
    mat_lines = "\n".join(lines)
    tone_cn = "formal" if tone == "formal" else "friendly"
    system = "You are a procurement assistant. Write a " + tone_cn + " chase email body in Chinese. No subject line."
    tpl_part = ("Reference template:\n" + template) if template else ""
    user = "Materials to chase:\n" + mat_lines + "\n\n" + tpl_part
    return call_llm(system, user, max_tokens=800)
