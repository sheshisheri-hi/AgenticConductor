"""Export closed defects to Conductor's issues_raw.json schema."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


def _get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req = Request(url, headers=headers or {"Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=60) as resp:  # noqa: S310 — controlled URL from CLI
        return json.loads(resp.read().decode("utf-8"))


def export_github_issues(
    owner: str,
    repo: str,
    *,
    state: str = "closed",
    labels: str | None = None,
    per_page: int = 30,
    max_pages: int = 3,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch GitHub issues (not PRs) into a normalized raw list."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "conductor-rca-export",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    items: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        q = f"state={state}&per_page={per_page}&page={page}"
        if labels:
            q += f"&labels={quote(labels)}"
        url = f"https://api.github.com/repos/{owner}/{repo}/issues?{q}"
        batch = _get_json(url, headers=headers)
        if not batch:
            break
        for issue in batch:
            if "pull_request" in issue:
                continue
            items.append(
                {
                    "id": str(issue.get("number")),
                    "source": "github",
                    "title": issue.get("title") or "",
                    "body": issue.get("body") or "",
                    "state": issue.get("state") or "",
                    "html_url": issue.get("html_url") or "",
                    "labels": [lbl.get("name") for lbl in (issue.get("labels") or []) if isinstance(lbl, dict)],
                    "created_at": issue.get("created_at"),
                    "closed_at": issue.get("closed_at"),
                    "repo": f"{owner}/{repo}",
                }
            )
    return items


def export_ado_work_items_stub_schema() -> dict[str, Any]:
    """Document the ADO → issues_raw shape (live fetch uses ADO REST via env)."""
    return {
        "schema_version": 1,
        "source": "ado",
        "required_fields": ["id", "title", "body", "html_url", "repo"],
        "notes": (
            "Use conductor_integrations.sources.ado.ADOClient for live pull, then "
            "normalize_ado_work_item() to this schema."
        ),
    }


def normalize_ado_work_item(raw: dict[str, Any], *, repo: str = "") -> dict[str, Any]:
    """Map an ADO WIT fields dict into issues_raw schema."""
    fields = raw.get("fields") or raw
    return {
        "id": str(raw.get("id") or fields.get("System.Id") or ""),
        "source": "ado",
        "title": fields.get("System.Title") or raw.get("title") or "",
        "body": fields.get("System.Description") or raw.get("description") or "",
        "state": fields.get("System.State") or raw.get("state") or "",
        "html_url": raw.get("url") or raw.get("html_url") or "",
        "labels": raw.get("labels") or [],
        "created_at": fields.get("System.CreatedDate"),
        "closed_at": fields.get("Microsoft.VSTS.Common.ClosedDate"),
        "repo": repo or fields.get("System.AreaPath") or "",
    }


def write_issues_raw(path: Path | str, items: list[dict[str, Any]], *, source: str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "source": source,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export defects to issues_raw.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gh = sub.add_parser("github", help="Export closed GitHub issues")
    gh.add_argument("--owner", required=True)
    gh.add_argument("--repo", required=True)
    gh.add_argument("--out", required=True)
    gh.add_argument("--state", default="closed")
    gh.add_argument("--labels", default=None)
    gh.add_argument("--per-page", type=int, default=30)
    gh.add_argument("--max-pages", type=int, default=2)
    gh.add_argument("--token", default=None, help="GitHub token (or GITHUB_TOKEN env)")

    ado = sub.add_parser("ado-schema", help="Print ADO issues_raw schema helper")
    ado.add_argument("--out", default=None)

    args = parser.parse_args(argv)
    if args.cmd == "github":
        import os

        token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("CONDUCTOR_GITHUB_TOKEN")
        items = export_github_issues(
            args.owner,
            args.repo,
            state=args.state,
            labels=args.labels,
            per_page=args.per_page,
            max_pages=args.max_pages,
            token=token,
        )
        path = write_issues_raw(args.out, items, source="github")
        print(f"Wrote {len(items)} issues → {path}")
    elif args.cmd == "ado-schema":
        schema = export_ado_work_items_stub_schema()
        if args.out:
            Path(args.out).write_text(json.dumps(schema, indent=2), encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print(json.dumps(schema, indent=2))


if __name__ == "__main__":
    main()
