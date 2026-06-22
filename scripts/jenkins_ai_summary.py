#!/usr/bin/env python3
"""Summarize Jenkins failure logs via Ollama or OpenAI-compatible API."""

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

# Common AWS / Ansible error codes in stderr
_AWS_ERROR = re.compile(r"\((\w+)\)\s+when calling")
_TASK_NAME = re.compile(r"TASK \[([^\]]+)\]")
_FATAL_STDERR = re.compile(r'"stderr":\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
_S3_BUCKET = re.compile(r"s3://([^/]+)/")
_BUCKET_DOES_NOT_EXIST = re.compile(
    r"The specified bucket does not exist|NoSuchBucket", re.I
)


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


def _decode_json_string(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace("\\n", " ").replace("\\\"", "\"")


def extract_failure_summary(log: str) -> str:
    """Build a short summary from the console log when AI is unavailable."""
    task_match = _TASK_NAME.search(log)
    task = task_match.group(1) if task_match else "build step"

    stderr = ""
    stderr_match = _FATAL_STDERR.search(log)
    if stderr_match:
        stderr = _decode_json_string(stderr_match.group(1))

    aws_code = ""
    aws_match = _AWS_ERROR.search(stderr or log)
    if aws_match:
        aws_code = aws_match.group(1)

    bucket = ""
    bucket_match = _S3_BUCKET.search(stderr or log)
    if bucket_match:
        bucket = bucket_match.group(1)

    # NoSuchBucket — short, actionable summary
    if aws_code == "NoSuchBucket" or _BUCKET_DOES_NOT_EXIST.search(stderr or log):
        target = f"bucket '{bucket}'" if bucket else "the S3 bucket"
        return (
            f"Failed: {task} — {target} does not exist ({aws_code or 'NoSuchBucket'}). "
            f"Create the bucket or update s3_bucket in the playbook."
        )

    if aws_code == "AccessDenied":
        return (
            f"Failed: {task} — AWS denied access ({aws_code}). "
            "Check IAM permissions for the Jenkins AWS credentials."
        )

    if stderr:
        detail = stderr.split("\n")[0].strip()
        if len(detail) > 200:
            detail = detail[:197] + "..."
        return f"Failed: {task} — {detail}"

    if "fatal:" in log.lower() or "FAILED!" in log:
        return f"Failed: {task} — see build console for details."

    return "Build failed — see console log for details."


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def ollama_model_name() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3.2")


def ollama_request(path: str, payload: dict | None = None, timeout: float = 30) -> dict | list:
    url = ollama_base_url() + path
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def ollama_is_reachable(timeout: float = 5) -> bool:
    try:
        ollama_request("/api/tags", timeout=timeout)
        return True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def start_ollama_server() -> None:
    if not shutil.which("ollama"):
        raise RuntimeError("ollama CLI not found; install Ollama on the Jenkins agent")

    print("Starting Ollama server...", file=sys.stderr)
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for attempt in range(60):
        if ollama_is_reachable(timeout=2):
            print("Ollama server is ready.", file=sys.stderr)
            return
        time.sleep(1)

    raise RuntimeError("Ollama server did not become ready within 60s")


def ensure_ollama_running() -> None:
    if ollama_is_reachable():
        return
    start_ollama_server()


def model_base_name(name: str) -> str:
    return name.split(":")[0]


def list_ollama_models() -> list[str]:
    data = ollama_request("/api/tags")
    models = data.get("models", [])
    return [str(item.get("name", "")) for item in models if item.get("name")]


def ollama_model_available(model: str, installed: list[str]) -> bool:
    target = model_base_name(model)
    return any(model_base_name(name) == target for name in installed)


def pull_ollama_model(model: str) -> None:
    timeout = int(os.environ.get("OLLAMA_PULL_TIMEOUT", "600"))
    url = ollama_base_url() + "/api/pull"
    body = json.dumps({"name": model, "stream": True}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )

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


def ensure_ollama_model(model: str) -> None:
    installed = list_ollama_models()
    if ollama_model_available(model, installed):
        print(f"Ollama model '{model}' is already available.", file=sys.stderr)
        return
    pull_ollama_model(model)


def prepare_ollama() -> tuple[str, str]:
    ensure_ollama_running()
    model = ollama_model_name()
    ensure_ollama_model(model)
    return ollama_base_url(), model


def call_ollama(prompt: str) -> str:
    base, model = prepare_ollama()
    url = base + "/api/generate"
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
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
    log = read_log()
    prompt = build_prompt(log)
    provider = os.environ.get("AI_PROVIDER", "ollama").lower()

    try:
        if provider == "openai":
            summary = call_openai_compatible(prompt)
        else:
            summary = call_ollama(prompt)
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
