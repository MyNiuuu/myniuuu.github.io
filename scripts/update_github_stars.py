#!/usr/bin/env python3
"""Refresh the shared star snapshot and render the homepage and repository list."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ARTICLE = re.compile(r"<article\b[^>]*>.*?</article>", re.S)
REPO_ATTRIBUTE = re.compile(r"\bdata-github-repo=[\"']([^\"']+)[\"']")
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
JST = timezone(timedelta(hours=9))
WORK_LABELS = {
    "alayalab/pwm": "Programmable-WM",
    "visionary-laboratory/visionary": "Visionary",
    "yifever20002/r3avatars": "R3-Avatar",
    "joseph-lin-tech/event_attack_physics": "Event-Attack",
}


def repository_for(article):
    opening_tag = article.split(">", 1)[0]
    match = REPO_ATTRIBUTE.search(opening_tag)
    if not match:
        return None
    name = match[1]
    if not REPO_NAME.fullmatch(name):
        raise ValueError(f"Invalid repository name: {name}")
    return name.lower()


def repositories_in(page):
    names = {repository_for(article[0]) for article in ARTICLE.finditer(page)}
    names.discard(None)
    if not names:
        raise ValueError("No paper repositories found; keeping the existing snapshot.")
    return sorted(names)


def fetch_repository(name):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "homepage-star-counter"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/repos/{name}", headers=headers)
    try:
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
        return {"id": data["id"], "name": data["full_name"], "stars": data["stargazers_count"]}
    except Exception as error:
        raise RuntimeError(f"Could not refresh {name}: {error}") from error


def build_snapshot(names, repositories, updated_at):
    """Validate the entire batch before replacing any saved values."""
    datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    unique = {}
    active = {}
    for name in names:
        repo = repositories[name]
        if type(repo["stars"]) is not int or repo["stars"] < 0:
            raise ValueError(f"Invalid star count for {name}")
        if type(repo["id"]) is not int or repo["id"] <= 0 or not REPO_NAME.fullmatch(repo["name"]):
            raise ValueError(f"Invalid repository metadata for {name}")
        # Repository IDs also deduplicate old URLs after a rename or transfer.
        if repo["id"] in unique and unique[repo["id"]]["stars"] != repo["stars"]:
            raise ValueError(f"Inconsistent counts for aliases of {name}; try again.")
        unique[repo["id"]] = repo
        active[name] = repo
    return {
        "updated_at": updated_at,
        "repository_count": len(unique),
        "total_stars": sum(repo["stars"] for repo in unique.values()),
        "repositories": active,
    }


def replace_block(text, kind, content):
    start = f"<!-- github-stars:{kind}:start -->"
    end = f"<!-- github-stars:{kind}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"Expected exactly one {kind} marker pair.")
    return re.sub(re.escape(start) + r".*?" + re.escape(end),
                  lambda _: start + content + end, text, flags=re.S)


def render_html(page, snapshot):
    date = datetime.fromisoformat(snapshot["updated_at"].replace("Z", "+00:00")).astimezone(JST)
    day = date.strftime("%Y-%m-%d")

    def render_article(match):
        article = match[0]
        name = repository_for(article)
        if name is None:
            return article
        repo = snapshot["repositories"][name]
        repo_name = escape(repo["name"], quote=True)
        badge = (
            f'<a class="paper-stars" href="https://github.com/{repo_name}" '
            f'aria-label="{repo_name} GitHub stars">'
            f'<img loading="lazy" src="https://img.shields.io/github/stars/{repo_name}?style=social" '
            f'alt="{repo_name} GitHub stars" height="16"></a>'
        )
        # New papers only need data-github-repo and their usual paper-links row.
        if "<!-- github-stars:badge:start -->" not in article:
            article, count = re.subn(
                r'(<p class="paper-links">.*?)(</p>)',
                lambda row: row[1].rstrip() + " <!-- github-stars:badge:start -->"
                "<!-- github-stars:badge:end -->" + row[2], article, count=1, flags=re.S)
            if count != 1:
                raise ValueError(f"Missing paper-links row for {name}")
        return replace_block(article, "badge", badge)

    page = ARTICLE.sub(render_article, page)
    total = f'{snapshot["total_stars"]:,}'
    count = snapshot["repository_count"]
    summary = (
        '\n          <div class="github-stars-summary">\n'
        f'            <a class="github-stars-total" href="github-stars.html" '
        f'title="Sum across {count} unique project repositories">'
        f'<span class="github-stars-number"><span class="github-star-icon" aria-hidden="true">☆</span> '
        f'<strong>{total}</strong></span> GitHub stars across research projects</a>\n'
        f'            <span class="github-stars-updated">Updated <time datetime="{day}">{day}</time></span>\n'
        '          </div>\n          '
    )
    return replace_block(page, "summary", summary)


def render_repository_list(snapshot):
    date = datetime.fromisoformat(snapshot["updated_at"].replace("Z", "+00:00")).astimezone(JST)
    day = date.strftime("%Y-%m-%d")
    unique = {repo["id"]: repo for repo in snapshot["repositories"].values()}
    rows = []
    for repo in sorted(unique.values(), key=lambda repo: (-repo["stars"], repo["name"].lower())):
        label = WORK_LABELS.get(repo["name"].lower(), repo["name"].split("/", 1)[1])
        rows.append(
            '        <li><div class="repository-row">'
            f'<a href="https://github.com/{escape(repo["name"], quote=True)}">{escape(label)}</a>'
            f'<span class="repository-stars">{repo["stars"]:,} {"star" if repo["stars"] == 1 else "stars"}</span></div></li>'
        )
    listing = "\n".join(rows)
    return f'''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="author" content="Muyao Niu">
    <title>GitHub Stars — Muyao Niu</title>
    <link rel="stylesheet" href="stylesheet.css">
  </head>
  <body>
    <main class="page repository-page">
      <a class="repository-back" href="index.html">← Muyao Niu</a>
      <h1>GitHub stars</h1>
      <p class="repository-description"><strong>{snapshot["total_stars"]:,}</strong> stars across {len(unique)} research project repositories.</p>
      <p class="repository-updated">Updated <time datetime="{day}">{day}</time> · Sorted by stars</p>
      <ol class="repository-list" aria-label="Research repositories, most starred first">
{listing}
      </ol>
    </main>
  </body>
</html>
'''


def refresh(root=ROOT, offline=False):
    page_path = root / "index.html"
    data_path = root / "data/github-stars.json"
    page = page_path.read_text(encoding="utf-8")
    names = repositories_in(page)
    if offline:
        old = json.loads(data_path.read_text(encoding="utf-8"))
        snapshot = build_snapshot(names, old["repositories"], old["updated_at"])
    else:
        # A failed request aborts the whole update, keeping the last complete batch.
        with ThreadPoolExecutor(max_workers=4) as pool:
            repositories = dict(zip(names, pool.map(fetch_repository, names)))
        snapshot = build_snapshot(names, repositories, datetime.now(timezone.utc).isoformat())
    rendered = render_html(page, snapshot)
    repository_list = render_repository_list(snapshot)
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    if page_path.read_text(encoding="utf-8") != page:
        raise RuntimeError("The homepage changed during the update; rerun to preserve the latest edits.")
    # All outputs are prepared before writing and are committed together.
    data_path.parent.mkdir(exist_ok=True)
    for path, content in [(data_path, serialized), (page_path, rendered),
                          (root / "github-stars.html", repository_list)]:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        if path.exists():
            temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    print(f'{snapshot["repository_count"]} repositories · {snapshot["total_stars"]:,} stars')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Render from the saved snapshot without network requests")
    args = parser.parse_args()
    try:
        refresh(offline=args.offline)
    except Exception as error:
        print(f"Star update failed: {error}", file=sys.stderr)
        sys.exit(1)
