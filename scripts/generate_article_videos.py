"""Generate 15-second article opening videos with HappyHorse 1.1 T2V."""
import argparse
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

DEFAULT_MODEL = "happyhorse-1.1-t2v"
DEFAULT_ENDPOINT = (
    "https://dashscope.aliyuncs.com"
    "/api/v1/services/aigc/video-generation/video-synthesis"
)
DEFAULT_RESOLUTION = "720P"
DEFAULT_RATIO = "16:9"
DEFAULT_DURATION = 15


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Chinese video prompt")
    parser.add_argument(
        "--out-dir", required=True, help="Output folder, e.g. article-dir/week5.2"
    )
    parser.add_argument(
        "--name-prefix", default="opening", help="File name prefix, e.g. week5.2_opening"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION,
        help="Video duration in seconds (HappyHorse accepts 3-15)",
    )
    parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        choices=["720P", "1080P"],
        help="Resolution tier",
    )
    parser.add_argument(
        "--ratio",
        default=DEFAULT_RATIO,
        choices=["16:9", "9:16", "1:1", "4:3", "3:4", "4:5", "5:4", "9:21", "21:9"],
        help="Aspect ratio",
    )
    parser.add_argument(
        "--watermark",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Add the HappyHorse watermark",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=15,
        help="Seconds between task status polls",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Maximum seconds to wait for the video task",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--api-key",
        default=None,
        help="DashScope API key; falls back to DASHSCOPE_API_KEY env var",
    )
    return parser.parse_args()


def get_api_key(args):
    key = args.api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit(
            "DASHSCOPE_API_KEY is not set. Export DASHSCOPE_API_KEY or pass --api-key."
        )
    return key


def build_payload(args):
    payload = {
        "model": args.model,
        "input": {"prompt": args.prompt},
        "parameters": {
            "resolution": args.resolution,
            "ratio": args.ratio,
            "duration": args.duration,
            "watermark": args.watermark,
        },
    }
    if args.seed is not None:
        payload["parameters"]["seed"] = args.seed
    return payload


def submit_task(args, key):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    response = requests.post(
        args.endpoint,
        headers=headers,
        json=build_payload(args),
        timeout=60,
    )
    if response.status_code != 200:
        raise SystemExit(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    if data.get("code"):
        raise SystemExit(f"API error: {data['code']} - {data.get('message', '')}")
    task_id = data["output"]["task_id"]
    print(f"task created: {task_id}")
    return task_id


def wait_for_video(args, task_id, key):
    parts = urlsplit(args.endpoint)
    task_url = f"{parts.scheme}://{parts.netloc}/api/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {key}"}
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        response = requests.get(task_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        output = data.get("output", {})
        status = output.get("task_status", "UNKNOWN")
        print(f"task status: {status}")
        if status == "SUCCEEDED":
            video_url = output.get("video_url")
            if not video_url:
                raise SystemExit(f"task succeeded without video_url: {data}")
            return video_url
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            raise SystemExit(
                f"task {status}: {output.get('code', '')} - "
                f"{output.get('message', '')}"
            )
        time.sleep(args.poll_interval)
    raise SystemExit(
        f"timed out after {args.timeout}s; poll {task_url} later with the task id"
    )


def download_video(args, video_url):
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name_prefix}.mp4"
    response = requests.get(video_url, stream=True, timeout=120)
    response.raise_for_status()
    with out_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            fh.write(chunk)
    print(f"saved: {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def main():
    args = parse_args()
    if not 3 <= args.duration <= 15:
        raise SystemExit("HappyHorse accepts video duration between 3 and 15 seconds")
    key = get_api_key(args)
    task_id = submit_task(args, key)
    video_url = wait_for_video(args, task_id, key)
    download_video(args, video_url)


if __name__ == "__main__":
    main()
