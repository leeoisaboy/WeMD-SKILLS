# WeMD-SKILLS

为 WeMD / 微信公众号 Markdown 文章生成中文配图，并自动上传到 `img.wemd.app` 图床的 Codex skill。

默认使用阿里云百炼 Qwen Image 3.0 文生图，火山引擎 Seedream 5.0 作为第一备用；HTML 透明概念图渲染器只作为最后兜底，仅在 Qwen 与 Seedream 都不可用时使用。

同时支持阿里云百炼 wan3.0-video（与 Qwen 同一套 Key）生成 15 秒文章片头视频，HappyHorse 1.1 T2V 作为备用，像电影开场一样形象地演绎整篇文章的核心内容，并插入公众号文章开头。

## 致谢与参考

本项目的 WeMD 配图工作流配套使用 [tenngoxars/WeMD](https://github.com/tenngoxars/WeMD)，这是一个开源的微信公众号 Markdown 编辑与发布工具。安装本 skill 后，可以先用 WeMD 编辑文章，再用本 skill 生成并上传配图。

## 功能

- 中文文生图：`qwen-image-3.0` 主用，`doubao-seedream-5-0-260128` 备用
- 板书式插画：每期固定一种板书材质（黑板、白板、牛皮纸、玻璃板、磁贴板等），手写中文加手绘图，图文并茂
- 15 秒文章片头：`wan3.0-video` 单段生成，`happyhorse-1.1-t2v` 备用，电影式开场演绎全文核心
- 片尾主题文字：`add_theme_text.py` 用毛笔字体重绘本期主题句，加马克笔划线并以渐变淡入方式叠加在片尾
- 公众号封面：2.35:1 封面图（1692x720），每期换一种明亮、行动导向的画风，以人物正在完成的具体动作承载文章核心隐喻
- 图床上传：自动上传 `img.wemd.app` 并替换 Markdown 中的本地图片路径
- 按周归档：每期插图保存到 `weekX.Y/` 子文件夹，方便管理
- HTML 透明图渲染（最后兜底）：仅在 Qwen 与 Seedream 都失败或不可用时使用

## 公众号

![一个AI产品经理的周记](assets/公众号图片.png)

本项目生成的插画会实际用于公众号「一个AI产品经理的周记」，那里可以看到 Qwen / Seedream 插画与 WeMD 排版结合后的真实效果，以及每期 AI 产品经理实习周记的完整文章。

在微信搜索「一个AI产品经理的周记」即可关注，也欢迎把本项目的插图效果转发给同样在关注 AI 产品经理成长的朋友。

## 目录结构

```text
WeMD-SKILLS/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── week3_concept_diagrams.html
├── scripts/
│   ├── generate_article_videos.py # wan3.0-video 15 秒文章片头（HappyHorse 备用）
│   ├── add_theme_text.py            # 片尾主题文字：毛笔艺术字 + 渐变淡入
│   ├── generate_qwen_images.py      # Qwen Image 3.0 文生图
│   ├── generate_seedream_images.py  # Seedream 5.0 备用生图
│   ├── render_html_diagrams.py      # HTML 透明概念图渲染（最后兜底）
│   └── upload_wemd_images.py        # 上传 img.wemd.app 并替换链接
├── requirements.txt
├── .gitignore
└── README.md
```

## 安装

1. 克隆或下载本项目。
2. 将 `WeMD-SKILLS` 目录复制到 Codex skills 目录：
   - Windows：`C:\Users\<用户名>\.codex\skills\wemd-article-diagrams`
   - macOS / Linux：`~/.codex/skills/wemd-article-diagrams`
3. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```


## 使用

### 1. 配置 API Key

```powershell
$env:DASHSCOPE_API_KEY = "你的百炼 Key"   # Qwen 主用
$env:ARK_API_KEY = "你的火山 Ark Key"      # Seedream 备用
```

### 2. wan3.0-video 生成 15 秒文章片头

```bash
python scripts/generate_article_videos.py \
  --prompt "<15秒片头分镜描述>" \
  --out-dir <article-dir>/<week-slug> \
  --name-prefix <week-slug>_opening \
  --duration 15 \
  --resolution 720P \
  --ratio 16:9
```

生成后在文章开头插入 `<video>` 预览块，发布到公众号时再到公众号后台插入正式视频。

视频模型不会写中文标题，片尾主题文字先用毛笔字体渲染成艺术字，再渐变淡入到视频结尾：

```bash
python scripts/add_theme_text.py \
  --video week8.2/week8.2_opening.mp4 \
  --text "借别人的鲁棒性|解自己的数据荒" \
  --fade-start 11.8 \
  --fade-duration 2.4 \
  --y-center 0.32
```

`--text` 用 `|` 分行，`--ink-color` 与 `--underline-color` 用来贴合当期的墨水与马克笔配色，`--no-underline` 可在板书没有马克笔划线时关闭下划线。

### 3. Qwen Image 3.0 生图

```bash
python scripts/generate_qwen_images.py \
  --prompt "<中文插画描述>" \
  --out-dir <article-dir>/<week-slug> \
  --name-prefix <week-slug> \
  --index 1 \
  --size 1024*1024
```

### 4. Seedream 5.0 备用生图

```bash
python scripts/generate_seedream_images.py \
  --prompt "<中文插画描述>" \
  --out-dir <article-dir>/<week-slug> \
  --name-prefix <week-slug> \
  --count 6 \
  --response-format b64_json
```

### 5. HTML 兜底（最后手段）

仅在 Qwen 与 Seedream 都失败或不可用时使用：

```bash
python scripts/render_html_diagrams.py \
  --html <article-dir>/<week-slug>/<week-slug>_concept_diagrams.html \
  --out-dir <article-dir>/<week-slug>
```

### 6. 上传到 img.wemd.app

在 Markdown 中使用子文件夹路径引用图片：

```markdown
![说明文字](week4.2/week4.2.1.png)
```

然后运行：

```bash
python scripts/upload_wemd_images.py week4.2.md
```

## 安全提示

- API Key 通过环境变量或 `--api-key` 传入，请勿提交到仓库。
- 百炼业务空间 Key 只在调用时从本机 CSV 读取（`默认业务空间-apiKey-*.csv`），仓库内不写入任何 Key；`.gitignore` 已忽略 `*.csv`、`*apiKey*`、`*api-key*`、`.env*` 等敏感文件。
- `wemd_upload_cache.json`、生成图片、`__pycache__` 已在 `.gitignore` 中忽略。

## License

MIT
