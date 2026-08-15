"""Generate Chinese article illustrations with Volcano Engine Seedream 5.0."""
import argparse
import base64
import os
import sys
from pathlib import Path

import requests
from openai import OpenAI

DEFAULT_MODEL = "doubao-seedream-5-0-260128"
DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_SIZE = "2K"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Chinese illustration prompt")
    parser.add_argument("--out-dir", required=True, help="Output folder, e.g. article-dir/week4.2")
    parser.add_argument("--name-prefix", default="seedream", help="File name prefix, e.g. week4.2")
    parser.add_argument("--count", type=int, default=1, help="Number of coherent images (max_images)")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="Image size, e.g. 1K / 2K / 4K")
    parser.add_argument("--response-format", choices=["url", "b64_json"], default="b64_json")
    parser.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=None, help="ARK API key; falls back to ARK_API_KEY env var")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    return parser.parse_args()


def get_api_key(args):
    key = args.api_key or os.environ.get("ARK_API_KEY")
    if not key:
        raise SystemExit(
            "ARK_API_KEY is not set. Export ARK_API_KEY or pass --api-key."
        )
    return key


def save_from_url(url, out_path):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    out_path.write_bytes(response.content)


def save_from_b64(b64, out_path):
    out_path.write_bytes(base64.b64decode(b64))


def main():
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI(
        base_url=args.base_url,
        api_key=get_api_key(args),
    )
    response = client.images.generate(
        model=args.model,
        prompt=args.prompt,
        size=args.size,
        response_format=args.response_format,
        stream=True,
        extra_body={
            "watermark": args.watermark,
            "sequential_image_generation": "auto",
            "sequential_image_generation_options": {
                "max_images": args.count,
            },
        },
    )

    saved = 0
    for event in response:
        if event is None:
            continue
        event_type = getattr(event, "type", "")
        if event_type == "image_generation.partial_failed":
            error = getattr(event, "error", None)
            print(f"partial failed: {error}", file=sys.stderr)
            continue
        if event_type == "image_generation.partial_succeeded":
            error = getattr(event, "error", None)
            if error is not None:
                print(f"partial error: {error}", file=sys.stderr)
                continue
            saved += 1
            out_path = out_dir / f"{args.name_prefix}.{saved}.png"
            if out_path.exists() and not args.overwrite:
                raise SystemExit(f"output exists, pass --overwrite: {out_path}")
            b64 = getattr(event, "b64_json", None)
            url = getattr(event, "url", None)
            if b64:
                save_from_b64(b64, out_path)
            elif url:
                save_from_url(url, out_path)
            else:
                print(f"partial succeeded without image data: {out_path}", file=sys.stderr)
                continue
            print(f"saved: {out_path}")
        elif event_type == "image_generation.completed":
            usage = getattr(event, "usage", None)
            if usage is not None:
                print("usage:", usage)

    if saved == 0:
        raise SystemExit("no images were generated")


if __name__ == "__main__":
    main()
