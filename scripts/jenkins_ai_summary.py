#!/usr/bin/env python3
"""Summarize Jenkins failure logs via configured AI provider or log parsing."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

# Failure line markers — scanned from bottom of log for the most recent failure.
_FAILURE_LINE = re.compile(
    r"fatal:\s*\[[^\]]+\]:\s*FAILED!"
    r"|FAILED!\s*=>"
    r"|ERROR:\s*"
    r"|BUILD FAILED"
    r"|Script returned exit code"
    r"|non-zero return code"
    r"|Traceback \(most recent call last\)"
    r"|npm ERR!"
    r"|FAILURE:"
    r"|command not found"
    r"|No such file or directory"
    r"|Permission denied"
    r"|An error occurred \("
    r"|Exception in thread"
    r"|FATAL ERROR"
    r"|AssertionError"
    r"|Error:\s+",
    re.I,
)

_TASK = re.compile(r"TASK \[([^\]]+)\]")
_STAGE = re.compile(r"stage\s*\{?\s*['\"]?([^'\"}\s]+)", re.I)
_FATAL_HOST = re.compile(r"fatal:\s*\[([^\]]+)\]:", re.I)
_JSON_FIELD = re.compile(r'"(stderr|msg|message)":\s*"((?:[^"\\]|\\.)*)"')
_AWS_CODE = re.compile(r"An error occurred \((\w+)\)", re.I)
_EXIT_CODE = re.compile(r"(?:exit code|return code)\s+(\d+)", re.I)
_JENKINS_ERROR = re.compile(r"ERROR:\s*(.+)", re.I)


@dataclass
class FailureInfo:
    component: str = ""
    message: str = ""
    error_code: str = ""
    source: str = "unknown"


def read_log() -> str:
    path = os.environ.get("FAILURE_LOG_PATH", "failure-log.txt")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()[-8000:]
    except OSError:
        return "(log file not found)"


def _decode_json_string(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace("\\n", " ").replace("\\\"", "\"").replace("\\t", " ")


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\+\s*", "", line)  # shell trace prefix
    return line.strip()


def _truncate(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _find_failure_anchor(log: str) -> int:
    lines = log.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if _FAILURE_LINE.search(lines[index]):
            return index
    return max(0, len(lines) - 1)


def _last_task_before(lines: list[str], anchor: int) -> str:
    for index in range(anchor, -1, -1):
        match = _TASK.search(lines[index])
        if match:
            return match.group(1)
    match = _TASK.search("\n".join(lines))
    return match.group(1) if match else ""


def _extract_json_fields(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), _decode_json_string(m.group(2))) for m in _JSON_FIELD.finditer(text)]


def detect_failure(log: str) -> FailureInfo:
    lines = [_clean_line(line) for line in log.splitlines()]
    anchor = _find_failure_anchor(log)
    window = lines[max(0, anchor - 12) : min(len(lines), anchor + 10)]
    window_text = "\n".join(window)

    info = FailureInfo()
    info.component = _last_task_before(lines, anchor)

    stage_match = _STAGE.search(window_text)
    if stage_match and not info.component:
        info.component = stage_match.group(1)

    host_match = _FATAL_HOST.search(window_text)
    if host_match and not info.component:
        info.component = host_match.group(1)

    for field, value in _extract_json_fields(window_text):
        if value and (field == "stderr" or not info.message):
            info.message = value
            info.source = "ansible"

    aws_match = _AWS_CODE.search(info.message or window_text)
    if aws_match:
        info.error_code = aws_match.group(1)

    exit_match = _EXIT_CODE.search(window_text)
    if exit_match and not info.error_code:
        info.error_code = f"exit {exit_match.group(1)}"

    for line in reversed(window):
        if not info.message:
            jenkins_match = _JENKINS_ERROR.search(line)
            if jenkins_match:
                info.message = jenkins_match.group(1).strip()
                info.source = "jenkins"
                break

            if _FAILURE_LINE.search(line) and not line.endswith("FAILED! =>"):
                info.message = line
                info.source = "log"
                break

    if not info.message:
        for line in reversed(window):
            if line and not line.startswith("[Pipeline]"):
                info.message = line
                break

    return info


def format_failure_summary(info: FailureInfo) -> str:
    label = info.component or "build step"
    detail = _truncate(info.message)
    if info.error_code and info.error_code not in detail:
        detail = f"{detail} ({info.error_code})" if detail else info.error_code
    if detail:
        return f"Failed: {label} — {detail}"
    return f"Failed: {label} — see build console for details."


def extract_failure_summary(log: str) -> str:
    return format_failure_summary(detect_failure(log))


def build_prompt(log: str, failure: FailureInfo) -> str:
    detected = format_failure_summary(failure)
    return f"""You are a CI/CD assistant. Summarize this Jenkins build failure.

Return plain text with:
1) What failed
2) Likely root cause
3) Suggested fix (1-3 concrete steps)

Keep it under 12 lines.

Job: {os.environ.get("JOB_NAME", "unknown")}
Build: #{os.environ.get("BUILD_NUMBER", "unknown")}
URL: {os.environ.get("BUILD_URL", "unknown")}

Detected failure hint: {detected}

Console log (tail):
{log}
"""


def resolve_provider() -> str:
    explicit = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if explicit:
        return explicit

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("AI_BASE_URL")
    model = os.environ.get("AI_MODEL") or os.environ.get("OPENAI_MODEL")

    if api_key or (base_url and model):
        return "openai"

    return "ollama"


def _http_json(
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 120,
) -> dict | list:
    data = None
    req_headers: dict[str, str] = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=req_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _model_base(name: str) -> str:
    return name.split(":")[0]


def _ollama_url() -> str:
    return (os.environ.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")


def _ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL") or os.environ.get("AI_MODEL") or "llama3.2"


def _ollama_request(path: str, payload: dict | None = None, timeout: float = 30) -> dict | list:
    return _http_json(_ollama_url() + path, payload, timeout=timeout)


def _ollama_reachable(timeout: float = 5) -> bool:
    try:
        _ollama_request("/api/tags", timeout=timeout)
        return True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def _start_ollama_server() -> None:
    if not shutil.which("ollama"):
        raise RuntimeError("ollama CLI not found; install Ollama on the Jenkins agent")

    print("Starting Ollama server...", file=sys.stderr)
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(60):
        if _ollama_reachable(timeout=2):
            print("Ollama server is ready.", file=sys.stderr)
            return
        time.sleep(1)

    raise RuntimeError("Ollama server did not become ready within 60s")


def _ensure_ollama_running() -> None:
    if _ollama_reachable():
        return
    _start_ollama_server()


def _list_ollama_models() -> list[str]:
    data = _ollama_request("/api/tags")
    return [str(item["name"]) for item in data.get("models", []) if item.get("name")]


def _ollama_model_installed(model: str, installed: list[str]) -> bool:
    base = _model_base(model)
    return any(_model_base(name) == base for name in installed)


def _pull_ollama_model(model: str) -> None:
    timeout = int(os.environ.get("OLLAMA_PULL_TIMEOUT", "600"))
    url = _ollama_url() + "/api/pull"
    body = json.dumps({"name": model, "stream": True}).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    print(f"Pulling Ollama model '{model}' (timeout {timeout}s)...", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            status = data.get("status")
            if status:
                print(status, file=sys.stderr)


def _ensure_ollama_model(model: str) -> None:
    installed = _list_ollama_models()
    if _ollama_model_installed(model, installed):
        print(f"Ollama model '{model}' is already available.", file=sys.stderr)
        return
    _pull_ollama_model(model)


def summarize_with_ollama(prompt: str) -> str:
    _ensure_ollama_running()
    model = _ollama_model()
    _ensure_ollama_model(model)

    data = _ollama_request(
        "/api/generate",
        {"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    return str(data.get("response", "")).strip()


def summarize_with_openai(prompt: str) -> str:
    base = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("AI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY") or ""
    model = os.environ.get("AI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or AI_API_KEY is not set")

    data = _http_json(
        f"{base}/chat/completions",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "Summarize CI/CD failures clearly and briefly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    return data["choices"][0]["message"]["content"].strip()


def summarize_with_ai(prompt: str, provider: str) -> str:
    providers: dict[str, Callable[[str], str]] = {
        "ollama": summarize_with_ollama,
        "openai": summarize_with_openai,
    }
    handler = providers.get(provider)
    if not handler:
        raise RuntimeError(f"Unsupported AI_PROVIDER: {provider}")
    return handler(prompt)


def main() -> int:
    log = read_log()
    failure = detect_failure(log)
    prompt = build_prompt(log, failure)
    provider = resolve_provider()

    print(f"Using AI provider: {provider}", file=sys.stderr)

    try:
        summary = summarize_with_ai(prompt, provider)
        header = "========== AI FAILURE SUMMARY =========="
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        json.JSONDecodeError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as err:
        print(f"AI unavailable ({err}), using log-based summary.", file=sys.stderr)
        summary = extract_failure_summary(log)
        header = "========== FAILURE SUMMARY (log-based) =========="

    print(header)
    print(summary)
    print("=" * len(header))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
