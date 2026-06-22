#!/usr/bin/env python3
"""Summarize Jenkins failure logs via Ollama or OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def read_log() -> str:
    path = os.environ.get("FAILURE_LOG_PATH", "failure-log.txt")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()[-8000:]
    except OSError:
        return "(log file not found)"


def build_prompt(log: str) -> str:
    return f"""You are a CI/CD assistant. Summarize this Jenkins build failure.

Return plain text with:
1) What failed
2) Likely root cause
3) Suggested fix (1-3 concrete steps)

Keep it under 12 lines.

Job: {os.environ.get("JOB_NAME", "unknown")}
Build: #{os.environ.get("BUILD_NUMBER", "unknown")}
URL: {os.environ.get("BUILD_URL", "unknown")}

Console log (tail):
{log}
"""


def call_ollama(prompt: str) -> str:
    url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
    body = json.dumps(
        {
            "model": os.environ.get("OLLAMA_MODEL", "llama3.2"),
            "prompt": prompt,
            "stream": False,
        }
    ).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.load(response)
    return str(data.get("response", "")).strip()


def call_openai_compatible(prompt: str) -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    url = f"{base}/chat/completions"
    body = json.dumps(
        {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": "Summarize CI/CD failures clearly and briefly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
    ).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.load(response)
    return data["choices"][0]["message"]["content"].strip()


def main() -> int:
    prompt = build_prompt(read_log())
    provider = os.environ.get("AI_PROVIDER", "ollama").lower()

    try:
        if provider == "openai":
            summary = call_openai_compatible(prompt)
        else:
            summary = call_ollama(prompt)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as err:
        print(f"AI summary unavailable: {err}", file=sys.stderr)
        return 1

    print("========== AI FAILURE SUMMARY ==========")
    print(summary)
    print("========================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
