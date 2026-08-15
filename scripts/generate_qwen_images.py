"""Generate Chinese article illustrations with Alibaba Cloud Qwen Image 3.0."""
import argparse
import os
import sys
from pathlib import Path

import requests

DEFAULT_MODEL = "qwen-image-3.0"
DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
DEFAULT_SIZE = "1024*1024"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Chinese illustration prompt")
    parser.add_argument("--out-dir", required=True, help="Output folder, e.g. article-dir/week4.2")
    parser.add_argument("--name-prefix", default="qwen", help="File name prefix, e.g. week4.2")
    parser.add_argument("--index", type=int, default=1, help="1-based image index for the file name")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="Output size, e.g. 1024*1024 or 1024*1792")
    parser.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--prompt-extend", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--api-key", default=None, help="DashScope API key; falls back to DASHSCOPE_API_KEY env var")
    return parser.parse_args()


def get_api_key(args):
    key = args.api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit(
            "DASHSCOPE_API_KEY is not set. Export DASHSCOPE_API_KEY or pass --api-key."
        )
    return key


def main():
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "model": args.model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": args.prompt}],
                }
            ]
        },
        "parameters": {
            "prompt_extend": args.prompt_extend,
            "n": 1,
            "size": args.size,
            "watermark": args.watermark,
        },
    }
    headers = {
        "Authorization": f"Bearer {get_api_key(args)}",
        "Content-Type": "application/json",
    }
    response = requests.post(args.endpoint, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise SystemExit(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    if data.get("code"):
        raise SystemExit(f"API error: {data['code']} - {data.get('message', '')}")

    try:
        choices = data["output"]["choices"]
        image_url = choices[0]["message"]["content"][0]["image"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"unexpected API response: {data}") from exc

    image_response = requests.get(image_url, timeout=120)
    image_response.raise_for_status()
    out_path = out_dir / f"{args.name_prefix}.{args.index}.png"
    out_path.write_bytes(image_response.content)
    print(f"saved: {out_path}")
    usage = data.get("usage", {})
    if usage:
        print("usage:", usage)


if __name__ == "__main__":
    main()
