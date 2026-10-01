"""Очистка неиспользуемых deployment без изменения активных ботов и окружений."""

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


TEAM = "team_OIdVeiXMtcQdNxXpseWNqQtV"
ORIGINAL = "prj_PxYCE2N7xbM3xOq2XPqX8KYCPvY0"
TEST = "prj_3WEWtX8vujb0llpvmuA1Umovf623"
PROJECTS = (ORIGINAL, TEST)


def request(path, params=None, method="GET"):
    params = {**(params or {}), "teamId": TEAM}
    url = "https://api.vercel.com" + path + "?" + urllib.parse.urlencode(params)
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        raise RuntimeError("VERCEL_TOKEN не задан")
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Vercel API HTTP {exc.code}: {method} {path}") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise RuntimeError(f"Vercel API: ошибка ответа {method} {path}") from None


def all_pages(path, key, params=None, fetch=request):
    """Не разрешаем очистку по неполной или зацикленной выборке."""
    result, seen = [], set()
    query = {"limit": 100, **(params or {})}
    while True:
        data = fetch(path, query)
        if (not isinstance(data.get(key), list) or not isinstance(data.get("pagination"), dict)
                or "next" not in data["pagination"]):
            raise RuntimeError("Vercel API: неполная форма пагинации")
        result.extend(data[key])
        cursor = data["pagination"].get("next")
        if cursor is None:
            return result
        if cursor in seen:
            raise RuntimeError("Vercel API: повторный курсор пагинации")
        seen.add(cursor)
        query["until"] = cursor


def inventory(fetch=request):
    aliases = all_pages("/v4/aliases", "aliases", fetch=fetch)
    deployments, targets = [], []
    for project in PROJECTS:
        data = fetch("/v9/projects/" + project)
        if data.get("id") != project or not isinstance(data.get("targets"), dict):
            raise RuntimeError("Vercel API: не подтверждены проект и текущие deployments")
        targets.extend(t["id"] for t in data["targets"].values())
        for deployment in all_pages("/v6/deployments", "deployments",
                                    {"projectId": project}, fetch):
            if deployment.get("projectId", project) != project:
                raise RuntimeError("Vercel API: чужой проект в выборке")
            deployments.append({**deployment, "projectId": project})
    return {"aliases": aliases, "deployments": deployments, "targets": targets}


def plan(snapshot):
    protected = set(snapshot["targets"])
    for alias in snapshot["aliases"]:
        deployment = alias.get("deployment")
        if deployment:
            if not deployment.get("id"):
                raise RuntimeError("Vercel API: не подтверждена привязка alias")
            protected.add(deployment["id"])
    deployments = snapshot["deployments"]
    for project in PROJECTS:
        healthy = sorted((d for d in deployments if d["projectId"] == project
                          and d.get("target") == "production" and d.get("state") == "READY"),
                         key=lambda d: d["created"], reverse=True)
        protected.update(d["uid"] for d in healthy[:2])
    candidates = []
    for deployment in deployments:
        project = deployment["projectId"]
        if project not in PROJECTS or deployment["uid"] in protected:
            continue
        if project == ORIGINAL and deployment.get("target") == "production":
            continue
        if deployment.get("target") not in {None, "preview", "production"}:
            continue
        if deployment.get("state") not in {"READY", "ERROR", "CANCELED"}:
            continue
        candidates.append({key: deployment.get(key) for key in
                           ("uid", "projectId", "created", "target", "state")})
    return {"protected": sorted(protected), "candidates": candidates}


def apply_plan(initial, fetch=request):
    # Новые deployments не попадают в удаление, новые aliases отменяют удаление.
    fresh = plan(inventory(fetch))
    eligible = {d["uid"] for d in fresh["candidates"]}
    deleted = []
    for deployment in initial["candidates"]:
        uid = deployment["uid"]
        if uid not in eligible:
            continue
        detail = fetch("/v13/deployments/" + uid)
        if detail.get("projectId") != deployment["projectId"]:
            raise RuntimeError("Vercel API: проект deployment изменился")
        if detail.get("target") == "production" and deployment["projectId"] == ORIGINAL:
            raise RuntimeError("Удаление исходного production запрещено")
        fetch("/v13/deployments/" + uid, method="DELETE")
        deleted.append(uid)
    return deleted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Удалить подтверждённые неиспользуемые deployments")
    args = parser.parse_args()
    try:
        initial = plan(inventory())
        print(json.dumps(initial, ensure_ascii=False, indent=2))
        if args.apply:
            print(json.dumps({"deleted": apply_plan(initial)}, ensure_ascii=False))
    except (RuntimeError, KeyError, TypeError) as exc:
        # Ошибки формы данных не раскрывают ответ API или реквизиты.
        parser.exit(1, (str(exc) if isinstance(exc, RuntimeError) else "Неполные данные Vercel") + "\n")


if __name__ == "__main__":
    main()
