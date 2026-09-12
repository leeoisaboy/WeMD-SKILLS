"""Fade the issue theme line into the end of an opening video as hand-inked art text.

Renders the theme text with a brush/handwriting font, tints it like the issue's ink,
adds a marker underline, then overlays it on the video with a gradual alpha fade so
the closing seconds always show the correct Chinese characters.
"""
import argparse
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

INK_DEFAULT = (26, 54, 104)
ORANGE_DEFAULT = (238, 138, 58)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, help="Input MP4")
    parser.add_argument("--out", default=None, help="Output MP4; in-place when omitted")
    parser.add_argument("--text", required=True, help="Theme text; use | to split lines")
    parser.add_argument("--font", default=r"C:\Windows\Fonts\STXINGKA.TTF")
    parser.add_argument("--ink-color", default=None, help="Ink colour as R,G,B")
    parser.add_argument("--underline-color", default=None, help="Marker colour as R,G,B")
    parser.add_argument("--fade-start", type=float, default=None, help="Fade-in start in seconds")
    parser.add_argument("--fade-duration", type=float, default=2.4)
    parser.add_argument("--y-center", type=float, default=0.32, help="Text block centre as a fraction of height")
    parser.add_argument("--width-frac", type=float, default=0.78, help="Max text width as a fraction of width")
    parser.add_argument("--font-size", type=int, default=None)
    parser.add_argument("--no-underline", action="store_true")
    parser.add_argument("--seed", type=int, default=20260912)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--keep-overlay", action="store_true", help="Keep the generated PNG")
    return parser.parse_args()


def probe(ffprobe, video):
    command = [
        ffprobe, "-v", "error", "-show_entries",
        "stream=codec_type,width,height,duration:format=duration",
        "-of", "json", str(video),
    ]
    out = subprocess.run(command, capture_output=True, text=True, check=True).stdout
    import json
    data = json.loads(out)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise SystemExit(f"no video stream in {video}")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(video_stream.get("duration") or data.get("format", {}).get("duration") or 0)
    return int(video_stream["width"]), int(video_stream["height"]), duration, has_audio


def parse_color(value, fallback):
    if not value:
        return fallback
    parts = [int(p) for p in value.replace(" ", "").split(",")]
    if len(parts) != 3:
        raise SystemExit(f"color must be R,G,B: {value}")
    return tuple(parts)


def draw_ink_line(image, text, font, ink, seed):
    """Draw one line with a hand-written wobble and slightly uneven edges."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x = 0
    for char in text:
        box = draw.textbbox((0, 0), char, font=font)
        width = box[2] - box[0]
        dy = rng.uniform(-0.012, 0.012) * font.size
        draw.text((x - box[0], -box[1] + dy), char, font=font, fill=ink + (255,))
        x += width + rng.uniform(-0.01, 0.03) * font.size
    return layer, x


def build_overlay(args, width, height):
    ink = parse_color(args.ink_color, INK_DEFAULT)
    marker = parse_color(args.underline_color, ORANGE_DEFAULT)
    lines = [line.strip() for line in args.text.split("|") if line.strip()]
    if not lines:
        raise SystemExit("--text is empty")

    if args.font_size:
        size = args.font_size
    else:
        size = int(min(width * args.width_frac / max(len(line) for line in lines) * 1.28,
                       height * args.width_frac / len(lines) * 0.92))
    font = ImageFont.truetype(args.font, size)
    spacing = int(size * 0.32)

    probe_image = Image.new("RGBA", (10, 10))
    probe_draw = ImageDraw.Draw(probe_image)
    widths = [probe_draw.textbbox((0, 0), line, font=font)[2] for line in lines]
    block_height = size * len(lines) + spacing * (len(lines) - 1)

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    top = int(height * args.y_center - block_height / 2)

    y = top
    last_width = widths[-1]
    for index, (line, line_width) in enumerate(zip(lines, widths)):
        x = int((width - line_width) / 2)
        rendered, drawn_width = draw_ink_line(
            Image.new("RGBA", (int(line_width + size), int(size * 1.6)), (0, 0, 0, 0)),
            line, font, ink, args.seed + index,
        )
        rendered = rendered.rotate(
            random.Random(args.seed + index).uniform(-1.1, 1.1),
            resample=Image.BICUBIC, expand=False,
        )
        overlay.alpha_composite(rendered, (x - int((rendered.width - line_width) / 2), int(y - size * 0.3)))
        shadow.alpha_composite(rendered, (x - int((rendered.width - line_width) / 2) + int(size * 0.045),
                                          int(y - size * 0.3) + int(size * 0.05)))
        y += size + spacing

    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.055))
    shadow.putalpha(shadow.getchannel("A").point(lambda a: int(a * 0.42)))
    shadow.putdata([(14, 20, 32, p[3]) for p in shadow.getdata()])

    if not args.no_underline:
        marker_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        marker_draw = ImageDraw.Draw(marker_layer)
        stroke = max(6, int(size * 0.11))
        left = int((width - last_width * 1.06) / 2)
        right = left + int(last_width * 1.06)
        base_y = int(top + block_height + size * 0.12)
        for offset, alpha, thick in ((0, 165, 1.0), (int(stroke * 0.35), 120, 0.7), (-int(stroke * 0.3), 150, 0.85)):
            y_line = base_y + offset
            thick_px = max(3, int(stroke * thick))
            marker_draw.line([(left, y_line), (right, y_line - int(size * 0.03))],
                             fill=marker + (alpha,), width=thick_px)
            for point in ((left, y_line), (right, y_line - int(size * 0.03))):
                marker_draw.ellipse([point[0] - thick_px // 2, point[1] - thick_px // 2,
                                     point[0] + thick_px // 2, point[1] + thick_px // 2],
                                    fill=marker + (alpha,))
        overlay.alpha_composite(marker_layer)

    overlay = Image.alpha_composite(shadow, overlay)
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(0.4, size * 0.006)))
    return overlay


def main():
    args = parse_args()
    video = Path(args.video).resolve()
    if not video.exists():
        raise SystemExit(f"missing video: {video}")
    out_path = Path(args.out).resolve() if args.out else video
    width, height, duration, has_audio = probe(args.ffprobe, video)
    fade_start = args.fade_start if args.fade_start is not None else max(0.0, duration - args.fade_duration - 0.7)

    overlay = build_overlay(args, width, height)
    overlay_path = video.with_name(video.stem + "_theme.png")
    overlay.save(overlay_path)

    temporary = out_path.with_name(out_path.stem + ".tmp.mp4")
    command = [
        args.ffmpeg, "-y", "-i", str(video), "-i", str(overlay_path),
        "-filter_complex",
        f"[1:v]format=rgba,fade=t=in:st={fade_start:.2f}:d={args.fade_duration:.2f}:alpha=1[ov];"
        f"[0:v][ov]overlay=0:0:format=auto,format=yuv420p[v]",
        "-map", "[v]",
    ]
    if has_audio:
        command += ["-map", "0:a", "-c:a", "copy"]
    command += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", str(temporary)]
    subprocess.run(command, check=True)
    temporary.replace(out_path)
    if not args.keep_overlay:
        overlay_path.unlink()
    print(f"theme text '{args.text}' faded in at {fade_start:.2f}s -> {out_path}")


if __name__ == "__main__":
    main()
