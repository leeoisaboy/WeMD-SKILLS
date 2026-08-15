---
name: wemd-article-diagrams
description: Create Chinese illustrations for WeChat/WeMD markdown articles with Alibaba Cloud Qwen Image 3.0 (Seedream 5.0 as fallback), save them into per-week folders, upload them to the official img.wemd.app image host, and replace local image paths with https://img.wemd.app/... URLs. Use when generating article illustrations or concept images for WeMD/WeChat articles, including multi-image coherent illustration sets.
---

# WeMD Article Diagrams

## Workflow

1. Generate all new article illustrations with Alibaba Cloud Qwen Image 3.0:

   ```bash
   python scripts/generate_qwen_images.py \
     --prompt "<中文插画描述>" \
     --out-dir <article-dir>/<week-slug> \
     --name-prefix <week-slug> \
     --index <N> \
     --size 1024*1024
   ```

   It calls the DashScope multimodal generation endpoint with model `qwen-image-3.0`, saves each image as `<week-slug>.N.png` inside the week subfolder, and creates the folder automatically. For a set of different scenes, call the script once per image with `--index 1..N`; for a single coherent set, Seedream 5.0 remains the fallback.

2. Reference local images in the markdown with their subfolder path, e.g. `![...](week3.3/week3.3.1.png)`, then upload and replace the links:

   ```bash
   python scripts/upload_wemd_images.py <article.md>
   ```

   It POSTs multipart `file` to `https://api.wemd.app/upload`, rewrites each image as `![filename-without-ext](https://img.wemd.app/...)`, and caches URLs in `wemd_upload_cache.json` next to the markdown.
3. If Qwen is unavailable or a coherent sequential set is required, fall back to Seedream:

   ```bash
   python scripts/generate_seedream_images.py \
     --prompt "<中文插画描述>" \
     --out-dir <article-dir>/<week-slug> \
     --name-prefix <week-slug> \
     --count <N> \
     --response-format b64_json
   ```

4. Verify: generated PNGs exist and are nonblank, every `img.wemd.app` URL returns HTTP 200 for `image/*`, and the markdown contains no local image paths.

## Notes

- Qwen Image 3.0 handles Chinese text and prompts well, so prompts and in-image text should be written in Chinese.
- Qwen API Key is read from the `DASHSCOPE_API_KEY` environment variable by default; `generate_qwen_images.py` also accepts `--api-key` for a one-off override. Do not hardcode the key in prompts or scripts.
- Default Qwen request settings: model `qwen-image-3.0`, `size=1024*1024`, `watermark=false`, `prompt_extend=true`, HTTP sync endpoint `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`.
- Seedream fallback uses `ARK_API_KEY`; default settings are model `doubao-seedream-5-0-260128`, `size=2K`, `response_format=b64_json`, `stream=true`, `watermark=true`.
- The HTML-based transparent diagram renderer at `scripts/render_html_diagrams.py` is kept as a legacy fallback only for exact text-heavy diagrams that image models cannot render reliably.
- WeMD only displays images with `https://img.wemd.app/...` URLs; local relative paths render blank.
- Upload response shape: `{"success": true, "url": "...", "filename": "..."}`.
- Dependencies: Python, `requests`; `openai>=1.0` is only needed for the Seedream fallback. Chrome or Edge are no longer required.
- Keep all local PNGs for one article in its own week subfolder, e.g. `week3.3/`; never render them flat into the article folder.
- The upload cache `wemd_upload_cache.json` stays next to the markdown and reuses already-uploaded URLs.
