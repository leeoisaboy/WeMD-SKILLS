#!/usr/bin/env python3
"""Update the 'Weekly Notes' section in a GitHub Profile README after publishing a WeChat article.

Usage:
  python scripts/update_github_profile.py \
    --url "https://mp.weixin.qq.com/s/..." \
    --md path/to/article.md \
    [--title "文章标题"] \
    [--summary "一句话核心观点"] \
    [--date 2026-11-21] \
    [--repo leeoisaboy/leeoisaboy] \
    [--max-items 5] \
    [--dry-run]

Authentication (never hardcode tokens in this script):
  - Set environment variable GITHUB_TOKEN (classic PAT with `repo` scope or fine-grained PAT with Contents: Read & Write), OR
  - Be logged into GitHub CLI (`gh auth login`), OR
  - Pass `--local-repo <path>` to edit a local clone and run `git commit && git push`.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

START_MARKER = "<!-- WEEKLY_NOTES_START -->"
END_MARKER = "<!-- WEEKLY_NOTES_END -->"
DEFAULT_REPO = "leeoisaboy/leeoisaboy"
DEFAULT_MAX_ITEMS = 5


def extract_from_markdown(md_path: Path) -> tuple[str, str]:
    """Extract (title, one_line_summary) from a local Markdown article."""
    text = md_path.read_text(encoding="utf-8")
    # Strip YAML frontmatter if present
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    # Strip HTML blocks like <video>...</video>
    text = re.sub(r"<video[\s\S]*?</video>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)

    title = ""
    summary = ""

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if not title and s.startswith("# "):
            title = s[2:].strip()
            continue
        # Skip headings, images, blockquotes, horizontal rules, list items, code fences
        if s.startswith(("#", "![", ">", "---", "***", "```", "|")):
            continue
        # Clean inline markdown syntax
        clean = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", s)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        clean = re.sub(r"[*_`~]", "", clean).strip()
        if len(clean) >= 12:
            # Take first sentence or truncate cleanly
            m = re.split(r"[。！？!?]", clean, maxsplit=1)
            first_sent = m[0].strip()
            if len(first_sent) > 60:
                first_sent = first_sent[:58].rstrip("，,、；;") + "…"
            elif first_sent and not first_sent.endswith(("。", "！", "？", "…")):
                first_sent += "。"
            summary = first_sent
            break

    return title, summary


def update_weekly_notes_block(
    readme_text: str,
    date_str: str,
    title: str,
    url: str,
    summary: str,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> str:
    """Insert a new weekly note at the top of the marker block and keep at most `max_items`."""
    if START_MARKER not in readme_text or END_MARKER not in readme_text:
        raise ValueError(
            f"Could not find {START_MARKER} ... {END_MARKER} in README.md. "
            "Please add the markers to your profile README first."
        )

    pattern = re.compile(
        rf"({re.escape(START_MARKER)}\r?\n)(.*?)(\r?\n?{re.escape(END_MARKER)})",
        flags=re.DOTALL,
    )
    match = pattern.search(readme_text)
    if not match:
        raise ValueError("Failed to parse WEEKLY_NOTES marker block.")

    existing_lines = [
        ln.strip()
        for ln in match.group(2).splitlines()
        if ln.strip().startswith("- ")
    ]

    # Remove any existing entry with the same URL (idempotent re-runs)
    existing_lines = [ln for ln in existing_lines if f"({url})" not in ln]

    safe_title = title.replace("[", "【").replace("]", "】").strip()
    safe_summary = summary.strip()
    new_entry = f"- `{date_str}` | [{safe_title}]({url})"
    if safe_summary:
        new_entry += f" — {safe_summary}"

    updated_lines = [new_entry] + existing_lines[: max(0, max_items - 1)]
    replacement = match.group(1) + "\n".join(updated_lines) + "\n" + END_MARKER
    return readme_text[: match.start()] + replacement + readme_text[match.end() :]


def resolve_github_token(cli_token: str | None) -> str | None:
    if cli_token:
        return cli_token.strip()
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_token:
        return env_token.strip()
    try:
        res = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        tok = res.stdout.strip()
        if tok:
            return tok
    except Exception:
        pass
    return None


def github_api_request(url: str, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "WeMD-SKILLS-Profile-Updater",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed ({exc.code}): {body}") from exc


def update_via_local_repo(
    repo_dir: Path,
    date_str: str,
    title: str,
    url: str,
    summary: str,
    max_items: int,
    dry_run: bool,
) -> None:
    readme_path = repo_dir / "README.md"
    if not readme_path.exists():
        raise FileNotFoundError(f"README.md not found in {repo_dir}")

    if not dry_run:
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--rebase"], check=True)

    original = readme_path.read_text(encoding="utf-8")
    updated = update_weekly_notes_block(original, date_str, title, url, summary, max_items)

    if dry_run:
        print("[DRY RUN] Updated WEEKLY_NOTES block:")
        m = re.search(rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}", updated, flags=re.DOTALL)
        if m:
            print(m.group(0))
        return

    readme_path.write_text(updated, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_dir), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", f"docs: add weekly note ({date_str})"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_dir), "push"], check=True)
    print(f"Pushed updated README.md from local repo: {repo_dir}")


def update_via_api(
    repo: str,
    token: str,
    date_str: str,
    title: str,
    url: str,
    summary: str,
    max_items: int,
    dry_run: bool,
) -> None:
    api_url = f"https://api.github.com/repos/{repo}/contents/README.md"
    file_info = github_api_request(api_url, token, method="GET")
    original = base64.b64decode(file_info["content"]).decode("utf-8")
    updated = update_weekly_notes_block(original, date_str, title, url, summary, max_items)

    if dry_run:
        print("[DRY RUN] Updated WEEKLY_NOTES block:")
        m = re.search(rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}", updated, flags=re.DOTALL)
        if m:
            print(m.group(0))
        return

    b64_content = base64.b64encode(updated.encode("utf-8")).decode("ascii")
    res = github_api_request(
        api_url,
        token,
        method="PUT",
        payload={
            "message": f"docs: add weekly note ({date_str})",
            "content": b64_content,
            "sha": file_info["sha"],
        },
    )
    print(f"Updated {repo}/README.md -> {res['content']['html_url']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append a published WeChat article to GitHub Profile README Weekly Notes (keeps latest 5)."
    )
    parser.add_argument("--url", required=True, help="Permanent WeChat article URL (https://mp.weixin.qq.com/s/...)")
    parser.add_argument("--md", type=Path, help="Optional local Markdown file to auto-extract title & summary")
    parser.add_argument("--title", help="Article title (overrides title extracted from --md)")
    parser.add_argument("--summary", help="One-line takeaway (overrides summary extracted from --md)")
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="Publish date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"Target GitHub profile repo (default: {DEFAULT_REPO})")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS, help="Maximum notes to keep (default: 5)")
    parser.add_argument("--local-repo", type=Path, help="Optional local git clone path of profile repo")
    parser.add_argument("--token", help="GitHub token override (prefer GITHUB_TOKEN env var or `gh auth login`)")
    parser.add_argument("--dry-run", action="store_true", help="Preview the updated block without pushing")
    args = parser.parse_args()

    extracted_title, extracted_summary = ("", "")
    if args.md:
        if not args.md.exists():
            print(f"Error: Markdown file not found: {args.md}", file=sys.stderr)
            return 1
        extracted_title, extracted_summary = extract_from_markdown(args.md)

    title = (args.title or extracted_title).strip()
    summary = (args.summary if args.summary is not None else extracted_summary).strip()

    if not title:
        print("Error: Could not determine article title. Pass --title or --md with an H1 heading.", file=sys.stderr)
        return 1

    if args.local_repo:
        update_via_local_repo(
            args.local_repo, args.date, title, args.url.strip(), summary, args.max_items, args.dry_run
        )
        return 0

    token = resolve_github_token(args.token)
    if not token:
        print(
            "Error: No GitHub token found. Set GITHUB_TOKEN env var, run `gh auth login`, or pass --local-repo.",
            file=sys.stderr,
        )
        return 1

    update_via_api(args.repo, token, args.date, title, args.url.strip(), summary, args.max_items, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
