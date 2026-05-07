"""Quick connectivity test for ChaseBase LLM configuration.

Usage:
  python test_chat_llm.py --project-id default
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


def mask(v: str, keep: int = 4) -> str:
    if not v:
        return "(empty)"
    if len(v) <= keep * 2:
        return "*" * len(v)
    return v[:keep] + "..." + v[-keep:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--project-id", default="default")
    args = parser.parse_args()

    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path, override=False)

    print("=" * 68)
    print("ChaseBase Chat/LLM Quick Test")
    print("=" * 68)
    print(f"API_BASE      : {os.getenv('API_BASE', '')}")
    print(f"LLM_PROVIDER  : {os.getenv('LLM_PROVIDER', '')}")
    print(f"LLM_MODEL     : {os.getenv('LLM_MODEL', '')}")
    print(f"HTTPS_PROXY   : {os.getenv('HTTPS_PROXY', '')}")
    print(f"HTTP_PROXY    : {os.getenv('HTTP_PROXY', '')}")
    print(f"API_KEY       : {mask(os.getenv('API_KEY', ''))}")
    print("-" * 68)

    health_url = f"{args.base_url}/health"
    try:
        r = requests.get(health_url, timeout=8)
        print(f"[health] {health_url} -> {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"[health] FAILED: {e}")
        return 2

    chat_url = f"{args.base_url}/api/projects/{args.project_id}/chat"
    payload = {
        "message": "请用一句话回复：连通性测试",
        "history": [],
    }
    try:
        r = requests.post(chat_url, json=payload, timeout=45)
        print(f"[chat]   {chat_url} -> {r.status_code}")
        try:
            data = r.json()
        except Exception:
            print(r.text)
            return 3

        print("[chat] response:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])

        answer = str(data.get("answer", ""))
        if r.status_code == 200 and answer and "LLM 调用失败" not in answer:
            print("\n✅ Chat 调用成功，LLM 返回正常。")
            return 0

        print("\n⚠️ Chat 接口可达，但 LLM 仍有配置/网络问题，请检查 answer 字段。")
        return 1
    except Exception as e:
        print(f"[chat] FAILED: {e}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
