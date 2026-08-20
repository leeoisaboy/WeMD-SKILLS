"""Generate 15-second article opening videos with MiniMax H3, falling back to HappyHorse 1.1 T2V."""
import argparse
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

MINIMAX_MODEL = "MiniMax-H3"
MINIMAX_CREATE_URL = "https://api.minimaxi.com/v2/video_generation"
MINIMAX_QUERY_URL = "https://api.minimaxi.com/v2/query/video_generation/{task_id}"
MINIMAX_RESOLUTION = "768P"
MINIMAX_RATIO = "16:9"
MINIMAX_DURATION = 15

HAPPYHORSE_MODEL = "happyhorse-1.1-t2v"
HAPPYHORSE_ENDPOINT = (
    "https://dashscope.aliyuncs.com"
    "/api/v1/services/aigc/video-generation/video-synthesis"
)
HAPPYHORSE_RESOLUTION = "720P"
HAPPYHORSE_RATIO = "16:9"
HAPPYHORSE_DURATION = 15

DEFAULT_PROVIDER = "minimax"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Chinese video prompt")
    parser.add_argument(
        "--out-dir", required=True, help="Output folder, e.g. article-dir/week5.3"
    )
    parser.add_argument(
        "--name-prefix", default="opening", help="File name prefix, e.g. week5.3_opening"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=MINIMAX_DURATION,
        help="Video duration in seconds (MiniMax 4-15, HappyHorse 3-15)",
    )
    parser.add_argument(
        "--resolution",
        default=MINIMAX_RESOLUTION,
        choices=["768P", "2K", "720P", "1080P"],
        help="Resolution tier; MiniMax 768P is the 0.5 CNY/s option",
    )
    parser.add_argument(
        "--ratio",
        default=MINIMAX_RATIO,
        choices=["16:9", "9:16", "1:1", "4:3", "3:4", "4:5", "5:4", "9:21", "21:9"],
        help="Aspect ratio",
    )
    parser.add_argument(
        "--watermark",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Add the provider watermark",
    )
    parser.add_argument("--seed", type=int, default=None, help="HappyHorse random seed")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between task status polls",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Maximum seconds to wait for the video task",
    )
    parser.add_argument(
        "--provider",
        choices=["minimax", "happyhorse"],
        default=DEFAULT_PROVIDER,
        help="Video provider; MiniMax H3 is the default",
    )
    parser.add_argument(
        "--fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Retry with HappyHorse when MiniMax fails",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument(
        "--api-key",
        default=None,
        help="Provider API key; MiniMax uses MINIMAX_API_KEY, HappyHorse uses DASHSCOPE_API_KEY",
    )
    return parser.parse_args()


def get_provider_key(provider, api_key):
    if api_key:
        return api_key
    env_name = "MINIMAX_API_KEY" if provider == "minimax" else "DASHSCOPE_API_KEY"
    key = os.environ.get(env_name)
    if not key:
        raise RuntimeError(
            f"{env_name} is not set. Export {env_name} or pass --api-key."
        )
    return key


def build_minimax_payload(args):
    return {
        "model": args.model or MINIMAX_MODEL,
        "content": [{"type": "text", "text": args.prompt}],
        "duration": args.duration,
        "resolution": args.resolution,
        "ratio": args.ratio,
        "aigc_watermark": args.watermark,
    }


def submit_minimax_task(args, key):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    url = args.endpoint or MINIMAX_CREATE_URL
    response = requests.post(
        url,
        headers=headers,
        json=build_minimax_payload(args),
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"missing task_id: {data}")
    print(f"minimax task created: {task_id}")
    return task_id


def wait_for_minimax_video(args, task_id, key):
    headers = {"Authorization": f"Bearer {key}"}
    query_url = MINIMAX_QUERY_URL.format(task_id=task_id)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        response = requests.get(query_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        task = data.get("task", {})
        status = task.get("status", "UNKNOWN")
        print(f"minimax task status: {status}")
        if status == "succeeded":
            video_url = task.get("content", {}).get("url")
            if not video_url:
                raise RuntimeError(f"task succeeded without content.url: {data}")
            return video_url
        if status in ("failed", "cancelled"):
            raise RuntimeError(
                f"task {status}: {task.get('error', data)}"
            )
        time.sleep(args.poll_interval)
    raise RuntimeError(
        f"timed out after {args.timeout}s; poll task {task_id} later"
    )


def build_happyhorse_payload(args):
    payload = {
        "model": args.model or HAPPYHORSE_MODEL,
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


def submit_happyhorse_task(args, key):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    response = requests.post(
        args.endpoint or HAPPYHORSE_ENDPOINT,
        headers=headers,
        json=build_happyhorse_payload(args),
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    if data.get("code"):
        raise RuntimeError(f"API error: {data['code']} - {data.get('message', '')}")
    task_id = data["output"]["task_id"]
    print(f"happyhorse task created: {task_id}")
    return task_id


def wait_for_happyhorse_video(args, task_id, key):
    parts = urlsplit(args.endpoint or HAPPYHORSE_ENDPOINT)
    task_url = f"{parts.scheme}://{parts.netloc}/api/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {key}"}
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        response = requests.get(task_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        output = data.get("output", {})
        status = output.get("task_status", "UNKNOWN")
        print(f"happyhorse task status: {status}")
        if status == "SUCCEEDED":
            video_url = output.get("video_url")
            if not video_url:
                raise RuntimeError(f"task succeeded without video_url: {data}")
            return video_url
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            raise RuntimeError(
                f"task {status}: {output.get('code', '')} - "
                f"{output.get('message', '')}"
            )
        time.sleep(args.poll_interval)
    raise RuntimeError(
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


def run_minimax(args):
    if not 4 <= args.duration <= 15:
        raise RuntimeError("MiniMax-H3 accepts video duration between 4 and 15 seconds")
    if args.resolution not in ("768P", "2K"):
        raise RuntimeError("MiniMax-H3 supports resolution 768P or 2K")
    if args.ratio not in ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16"):
        raise RuntimeError(
            "MiniMax-H3 text-to-video supports ratio 21:9, 16:9, 4:3, 1:1, 3:4, 9:16"
        )
    key = get_provider_key("minimax", args.api_key)
    task_id = submit_minimax_task(args, key)
    video_url = wait_for_minimax_video(args, task_id, key)
    download_video(args, video_url)


def run_happyhorse(args):
    if not 3 <= args.duration <= 15:
        raise RuntimeError("HappyHorse accepts video duration between 3 and 15 seconds")
    if args.resolution not in ("720P", "1080P"):
        raise RuntimeError("HappyHorse supports resolution 720P or 1080P")
    key = get_provider_key("happyhorse", args.api_key)
    task_id = submit_happyhorse_task(args, key)
    video_url = wait_for_happyhorse_video(args, task_id, key)
    download_video(args, video_url)


def main():
    args = parse_args()
    providers = [args.provider]
    if args.provider == "minimax" and args.fallback:
        providers.append("happyhorse")
    last_error = None
    for provider in providers:
        try:
            if provider == "minimax":
                run_minimax(args)
            else:
                run_happyhorse(args)
            return
        except Exception as exc:
            last_error = exc
            print(f"{provider} failed: {exc}")
    raise SystemExit(str(last_error))


if __name__ == "__main__":
    main()
