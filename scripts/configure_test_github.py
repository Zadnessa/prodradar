"""Автоматически настроить prodradar-test через Actions и проверить реальные API."""

import io
import json
import os
from pathlib import Path
import sys
import time
import uuid
import zipfile

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_test_github import prepare
from scripts.setup_test_github import REPOSITORY, SetupError

API = f"https://api.github.com/repos/{REPOSITORY}"
WORKFLOW = 372368844
REF = "codex/restore-test-bot"


def api_request(method, path, body=None, binary=False):
    token = os.environ["PRODRADAR_GITHUB_TOKEN"]
    response = requests.request(method, API + path,
                                headers={"Authorization": f"Bearer {token}",
                                         "Accept": "application/vnd.github+json"},
                                json=body, timeout=30)
    if not response.ok:
        raise SetupError(f"GitHub HTTP {response.status_code}; {method} {path}")
    if binary:
        return response.content
    return response.json() if response.content else None


def wait_run(run_id):
    deadline = time.monotonic() + 600
    last = None
    while time.monotonic() < deadline:
        run = api_request("GET", f"/actions/runs/{run_id}")
        if run["status"] != last:
            print(f"Actions {run_id}: {run['status']}", flush=True)
            last = run["status"]
        if run["status"] == "completed":
            if run["conclusion"] != "success":
                raise SetupError(f"Actions {run_id}: {run['conclusion']}; проверьте job setup_github и environment secret PRODRADAR_GITHUB_TOKEN")
            return run
        time.sleep(5)
    raise SetupError(f"Actions {run_id}: превышено время ожидания; запуск не повторяем автоматически")


def dispatch(phase, encrypted_settings=None):
    marker = uuid.uuid4().hex[:12]
    inputs = {"setup_github": phase, "setup_request": marker,
              "collect_test": False, "audit_sources": False}
    if encrypted_settings:
        inputs["encrypted_settings"] = json.dumps(encrypted_settings, separators=(",", ":"))
    previous = api_request("GET", f"/actions/workflows/{WORKFLOW}/runs?per_page=30")
    old_ids = {run["id"] for run in previous["workflow_runs"]}
    api_request("POST", f"/actions/workflows/{WORKFLOW}/dispatches", {"ref": REF, "inputs": inputs})
    title = f"Setup prodradar-test {phase} {marker}"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        runs = api_request("GET", f"/actions/workflows/{WORKFLOW}/runs?per_page=30")["workflow_runs"]
        matches = [run for run in runs if run["id"] not in old_ids and run["event"] == "workflow_dispatch"
                   and run["head_branch"] == REF and (phase == 'none' or run.get("display_title") == title)]
        if len(matches) == 1:
            return wait_run(matches[0]["id"])
        if len(matches) > 1:
            raise SetupError("Неоднозначный run ID; не продолжаем настройку")
        time.sleep(3)
    raise SetupError("Не найден запуск Actions; не повторяем dispatch автоматически")


def download_public_key(run_id):
    artifacts = api_request("GET", f"/actions/runs/{run_id}/artifacts")["artifacts"]
    matches = [row for row in artifacts if row["name"] == "github-environment-public-key" and not row["expired"]]
    if len(matches) != 1:
        raise SetupError("Не найден однозначный artifact публичного ключа")
    data = api_request("GET", f"/actions/artifacts/{matches[0]['id']}/zip", binary=True)
    # Из ZIP читается только ожидаемый публичный файл, без распаковки путей на диск.
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return json.loads(archive.read("github-environment-key.json"))


def main():
    if os.getenv("PRODRADAR_PROFILE") != "test":
        print("Запустите через scripts/run_profile.py --profile test configure-github", file=sys.stderr)
        return 1
    try:
        print("Получаем публичный ключ через Actions без изменения настроек", flush=True)
        exported = dispatch("export-key")
        public_key = download_public_key(exported["id"])
        print("Проверяем реальные test-реквизиты и шифруем в памяти", flush=True)
        settings = prepare(public_key)
        print("Обновляем только prodradar-test через Actions", flush=True)
        applied = dispatch("apply", settings)
        print("Проверяем настроенное окружение без сбора и рассылки", flush=True)
        checked = dispatch("none")
        print(f"Готово: setup Actions {applied['id']}; check Actions {checked['id']}", flush=True)
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Настройка остановлена: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
