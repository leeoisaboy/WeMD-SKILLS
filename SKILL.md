---
name: wemd-article-diagrams
description: Create Chinese illustrations and 15-second opening videos for WeChat/WeMD markdown articles with Alibaba Cloud Qwen Image 3.0, MiniMax H3 as the primary video model, HappyHorse 1.1 T2V as the video fallback, Seedream 5.0 as the first image fallback, and HTML diagrams only as the last resort. Save media into per-week folders, upload images to the official img.wemd.app image host, replace local image paths with https://img.wemd.app/... URLs, and place generated videos at the top of the article. Use when generating article illustrations, concept images, or opening videos for WeMD/WeChat articles, including multi-image coherent illustration sets.
---

# WeMD Article Diagrams

## Workflow

1. Generate the 15-second opening video with MiniMax H3 at 768P (the 0.50 元/秒 option):

   ```bash
   python scripts/generate_article_videos.py \
     --prompt "<15秒片头分镜描述>" \
     --out-dir <article-dir>/<week-slug> \
     --name-prefix <week-slug>_opening \
     --duration 15 \
     --resolution 768P \
     --ratio 16:9
   ```

   It submits one async task to `https://api.minimaxi.com/v2/video_generation` with model `MiniMax-H3` and saves `<week-slug>_opening.mp4` in the week subfolder. The script polls the task and downloads the finished MP4 automatically; if MiniMax fails, it retries with HappyHorse 1.1 T2V (`--provider happyhorse --resolution 720P`) unless `--no-fallback` is passed. The 15 seconds is the article's title sequence, like a movie opening: start with a visual hook, dramatize the article's core message through vivid motion, and end by landing on the theme. Use few words and strong images, and keep the same visual style as the issue's illustrations. Then insert the video block at the very top of the article, above the title:

   ```html
   <video controls preload="metadata" poster="week5.2/week5.2.1.png" width="100%">
     <source src="week5.2/week5.2_opening.mp4" type="video/mp4">
     你的浏览器不支持视频播放。
   </video>
   ```

2. Generate all new article illustrations with Alibaba Cloud Qwen Image 3.0:

   ```bash
   python scripts/generate_qwen_images.py \
     --prompt "<中文插画描述>" \
     --out-dir <article-dir>/<week-slug> \
     --name-prefix <week-slug> \
     --index <N> \
     --size 1024*1024
   ```

   It calls the DashScope multimodal generation endpoint with model `qwen-image-3.0`, saves each image as `<week-slug>.N.png` inside the week subfolder, and creates the folder automatically. For a set of different scenes, call the script once per image with `--index 1..N`.

3. Reference local images in the markdown with their subfolder path, e.g. `![...](week3.3/week3.3.1.png)`, then upload and replace the links:

   ```bash
   python scripts/upload_wemd_images.py <article.md>
   ```

   It POSTs multipart `file` to `https://api.wemd.app/upload`, rewrites each image as `![filename-without-ext](https://img.wemd.app/...)`, and caches URLs in `wemd_upload_cache.json` next to the markdown.
4. If Qwen is unavailable or fails, fall back to Seedream:

   ```bash
   python scripts/generate_seedream_images.py \
     --prompt "<中文插画描述>" \
     --out-dir <article-dir>/<week-slug> \
     --name-prefix <week-slug> \
     --count <N> \
     --response-format b64_json
   ```

5. Only if both Qwen and Seedream fail or are unavailable, use the HTML renderer as the last resort:

   ```bash
   python scripts/render_html_diagrams.py --html <article-dir>/<week-slug>/<week-slug>_concept_diagrams.html --out-dir <article-dir>/<week-slug>
   ```

   Use `assets/week3_concept_diagrams.html` as the style baseline for exact text-heavy diagrams. This is not a normal alternative to the image APIs; it exists only to keep the workflow running when every API fails.

6. Verify: generated PNGs and the opening MP4 exist and are nonblank, every `img.wemd.app` URL returns HTTP 200 for `image/*`, and the markdown contains no local image paths.

## Notes

- Qwen Image 3.0 handles Chinese text and prompts well, so prompts and in-image text should be written in Chinese.
- Illustration prompts must only use content already present in the article text. Never introduce company-confidential specifics (such as exact dialects, internal product names, or unpublicized hotwords) just because they appear in conversation or earlier drafts; if the article says "方言热词", the image must say "方言热词".
- Each issue must use a different illustration background style to avoid reader aesthetic fatigue. Before generating, pick a new visual style for the week, append a fixed style suffix to every image prompt in that set, and record the style in `## Per-issue visual style`.
- Qwen Image 3.0 reads its API key from `DASHSCOPE_API_KEY` or `--api-key`. The default public endpoint is `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`; if you use a dedicated Model Studio workspace, replace the host with your workspace endpoint and keep the key out of the repository.
- MiniMax H3 is the primary video provider. `generate_article_videos.py` defaults to model `MiniMax-H3`, `duration=15`, `resolution=768P` (0.50 元/秒), `ratio=16:9`, `aigc_watermark=false`. MiniMax accepts 4-15 seconds and supports text-to-video ratios `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`; text-only generation requires an explicit `ratio`. The async flow is POST `https://api.minimaxi.com/v2/video_generation`, then poll `https://api.minimaxi.com/v2/query/video_generation/{task_id}`; on `status=succeeded`, download `task.content.url` before the temporary URL expires.
- MiniMax API key is read from the `MINIMAX_API_KEY` environment variable by default; `generate_article_videos.py` also accepts `--api-key`. Do not hardcode the key into this skill, the scripts, or prompts.
- HappyHorse 1.1 T2V is the video fallback and uses the same DashScope API key as Qwen with the async service path: `https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis`. The request must include `X-DashScope-Async: enable`; the script then polls `.../api/v1/tasks/{task_id}` and downloads each finished MP4 before the temporary result URL expires. Run it explicitly with `--provider happyhorse --resolution 720P` (defaults: model `happyhorse-1.1-t2v`, `duration=15`, `ratio=16:9`, `watermark=false`). HappyHorse accepts 3-15 seconds; keep every article opening video at 15 seconds and design it as a movie-style title sequence.
- The official `api.wemd.app/upload` service accepts images only, so keep the MP4 local and preview it with the `<video>` block above. WeChat article bodies cannot embed an arbitrary MP4 URL directly; when publishing, upload the generated MP4 in the WeChat public account editor and replace the preview block with the editor-inserted video.
- Qwen API Key is read from the `DASHSCOPE_API_KEY` environment variable by default; `generate_qwen_images.py` also accepts `--api-key` for a one-off override. Do not hardcode the key in prompts or scripts.
- Default Qwen request settings: model `qwen-image-3.0`, `size=1024*1024`, `watermark=false`, `prompt_extend=true`, HTTP sync endpoint `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`. If you use a dedicated Model Studio workspace, replace the host with your workspace endpoint and keep the key out of the repository.
- Seedream fallback uses `ARK_API_KEY`; default settings are model `doubao-seedream-5-0-260128`, `size=2K`, `response_format=b64_json`, `stream=true`, `watermark=true`.
- The HTML-based transparent diagram renderer at `scripts/render_html_diagrams.py` is the last-resort fallback. Use it only after Qwen Image 3.0 and Seedream 5.0 both fail or are unavailable; it is not a normal alternative to the image APIs.
- WeMD only displays images with `https://img.wemd.app/...` URLs; local relative paths render blank.
- Upload response shape: `{"success": true, "url": "...", "filename": "..."}`.
- Dependencies: Python and `requests`; `openai>=1.0` is only needed for the Seedream fallback. Chrome or Edge are no longer required.
- Keep all local PNGs for one article in its own week subfolder, e.g. `week3.3/`; never render them flat into the article folder.
- Keep the opening MP4 in the same week subfolder as the images, e.g. `week5.2/week5.2_opening.mp4`.
- The upload cache `wemd_upload_cache.json` stays next to the markdown and reuses already-uploaded URLs.

## Per-issue visual style

Style history (append each new issue before generating):

- week3.x: 深绿色黑板 + 粉笔手绘科普信息图
- week4.x: 深绿色黑板 + 粉笔手绘科普信息图
- week5.1: 公司透明玻璃板 + 黑色/彩色油性马克笔手绘（玻璃隐约透出办公室背景）
- week5.2: 深蓝色工程蓝图图纸 + 白色/浅蓝针管笔手绘线稿、亮黄色重点标注

For each new issue, pick a visually distinct background and material, then describe it explicitly in every prompt. For example, week5.1 uses this style suffix:

```text
统一使用公司透明玻璃板背景：半透明玻璃幕墙表面，隐约透出模糊的办公区灯光与桌椅轮廓，玻璃上有轻微反光与擦拭痕迹；用黑色油性马克笔手绘线稿、图表、箭头与简笔小人，辅以红、蓝、绿马克笔标注重点，字迹为手写体；整体清晰现代、商务会议室感、讲解感强。
```
