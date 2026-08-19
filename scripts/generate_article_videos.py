"""Generate 30-second article opening videos with HappyHorse 1.1 T2V."""
import argparse
import math
import os
import subprocess
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
DEFAULT_DURATION = 30
MAX_CLIP_DURATION = 15


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Chinese video prompt")
    parser.add_argument(
        "--prompt-part-1",
        default=None,
        help="Optional explicit prompt for the first 15s clip",
    )
    parser.add_argument(
        "--prompt-part-2",
        default=None,
        help="Optional explicit prompt for the second 15s clip",
    )
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
        help="Target video duration in seconds; clips longer than the model limit are concatenated",
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
        help="Maximum seconds to wait for each clip task",
    )
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Path to ffmpeg")
    parser.add_argument(
        "--keep-clips",
        action="store_true",
        help="Keep the individual clip MP4 files after concatenation",
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


def clip_prompts(prompt, count, part1=None, part2=None):
    if count == 2 and part1 and part2:
        return [part1, part2]
    if count == 1:
        return [prompt]
    parts = []
    for index in range(1, count + 1):
        if count == 2:
            suffix = (
                "这是第1段：作为开场前半段，画面开始展开，节奏明快，结尾处为下一段留下自然衔接。"
                if index == 1
                else "这是第2段：画面承接第1段的场景与风格，自然延续并完成收尾，最后定格在核心信息上。"
            )
        else:
            suffix = f"这是第{index}段：与前一段自然衔接，节奏保持一致。"
        parts.append(f"{prompt} {suffix}")
    return parts


def build_payload(args, prompt, duration):
    payload = {
        "model": args.model,
        "input": {"prompt": prompt},
        "parameters": {
            "resolution": args.resolution,
            "ratio": args.ratio,
            "duration": duration,
            "watermark": args.watermark,
        },
    }
    if args.seed is not None:
        payload["parameters"]["seed"] = args.seed
    return payload


def submit_task(args, key, prompt, duration):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    response = requests.post(
        args.endpoint,
        headers=headers,
        json=build_payload(args, prompt, duration),
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


def download_video(out_path, video_url):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(video_url, stream=True, timeout=120)
    response.raise_for_status()
    with out_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            fh.write(chunk)
    print(f"saved: {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def concat_videos(clip_paths, out_path, ffmpeg):
    list_path = out_path.with_suffix(".concat.txt")
    with list_path.open("w", encoding="utf-8") as fh:
        for clip_path in clip_paths:
            fh.write(f"file '{clip_path.as_posix()}'\n")
    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(out_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed: {result.stderr[-2000:]}")
    print(f"saved: {out_path} ({out_path.stat().st_size} bytes)")
    list_path.unlink()


def main():
    args = parse_args()
    key = get_api_key(args)
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    clip_duration = min(args.duration, MAX_CLIP_DURATION)
    clip_count = math.ceil(args.duration / clip_duration)
    prompts = clip_prompts(
        args.prompt, clip_count, args.prompt_part_1, args.prompt_part_2
    )
    clip_paths = []

    try:
        for index, prompt in enumerate(prompts, start=1):
            remaining = args.duration - (index - 1) * clip_duration
            duration = min(clip_duration, remaining)
            task_id = submit_task(args, key, prompt, duration)
            video_url = wait_for_video(args, task_id, key)
            clip_path = out_dir / f"{args.name_prefix}.clip{index}.mp4"
            download_video(clip_path, video_url)
            clip_paths.append(clip_path)

        final_path = out_dir / f"{args.name_prefix}.mp4"
        if clip_count == 1:
            clip_paths[0].replace(final_path)
        else:
            concat_videos(clip_paths, final_path, args.ffmpeg)
    finally:
        if not args.keep_clips:
            for clip_path in clip_paths:
                if clip_path.exists():
                    clip_path.unlink()


if __name__ == "__main__":
    main()
