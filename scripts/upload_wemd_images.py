"""Upload local images referenced by a WeMD markdown file to img.wemd.app."""
import json
import re
import sys
from pathlib import Path

import requests

UPLOAD_URL = "https://api.wemd.app/upload"
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def load_cache(cache_file):
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return {}


def save_cache(cache_file, cache):
    cache_file.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upload_image(path):
    suffix = path.suffix.lower()
    if suffix not in MIME:
        raise ValueError(f"unsupported image type: {suffix}")
    with path.open("rb") as fh:
        response = requests.post(
            UPLOAD_URL,
            files={"file": (path.name, fh, MIME[suffix])},
            timeout=90,
        )
    response.raise_for_status()
    data = response.json()
    if not data.get("url"):
        raise RuntimeError(f"no url returned for {path.name}: {response.text}")
    return data["url"]


def verify_url(url):
    response = requests.head(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return response.status_code


def rewrite_md(md_path):
    md_path = Path(md_path)
    if not md_path.is_absolute():
        md_path = md_path.resolve()
    text = md_path.read_text(encoding="utf-8")
    cache_file = md_path.parent / "wemd_upload_cache.json"
    cache = load_cache(cache_file)
    changed = 0
    results = []

    def replace(match):
        nonlocal changed
        alt, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://", "data:")):
            return match.group(0)
        local = target[2:] if target.startswith("./") else target
        image_path = (md_path.parent / local).resolve()
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        key = str(image_path)
        if key not in cache:
            cache[key] = upload_image(image_path)
            save_cache(cache_file, cache)
            verify_url(cache[key])
        changed += 1
        results.append((image_path.name, cache[key]))
        return f"![{image_path.stem}]({cache[key]})"

    new_text = IMAGE_RE.sub(replace, text)
    md_path.write_text(new_text, encoding="utf-8")
    print(f"updated {md_path.name}: {changed} image(s)")
    for name, url in results:
        print(f"{name}: {url}")


if __name__ == "__main__":
    targets = sys.argv[1:] or ["week3.1.md"]
    for target in targets:
        rewrite_md(target)
