# WeMD-SKILLS

为 WeMD / 微信公众号 Markdown 文章生成中文配图，并自动上传到 `img.wemd.app` 图床的 Codex skill。

默认使用阿里云百炼 Qwen Image 3.0 文生图，火山引擎 Seedream 5.0 作为第一备用；HTML 透明概念图渲染器只作为最后兜底，仅在 Qwen 与 Seedream 都不可用时使用。

## 致谢与参考

本项目的 WeMD 配图工作流配套使用 [tenngoxars/WeMD](https://github.com/tenngoxars/WeMD)，这是一个开源的微信公众号 Markdown 编辑与发布工具。安装本 skill 后，可以先用 WeMD 编辑文章，再用本 skill 生成并上传配图。

## 功能

- 中文文生图：`qwen-image-3.0` 主用，`doubao-seedream-5-0-260128` 备用
- 图床上传：自动上传 `img.wemd.app` 并替换 Markdown 中的本地图片路径
- 按周归档：每期插图保存到 `weekX.Y/` 子文件夹，方便管理
- HTML 透明图渲染（最后兜底）：仅在 Qwen 与 Seedream 都失败或不可用时使用

## 公众号

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

### 2. Qwen Image 3.0 生图

```bash
python scripts/generate_qwen_images.py \
  --prompt "<中文插画描述>" \
  --out-dir <article-dir>/<week-slug> \
  --name-prefix <week-slug> \
  --index 1 \
  --size 1792*1024
```

### 3. Seedream 5.0 备用生图

```bash
python scripts/generate_seedream_images.py \
  --prompt "<中文插画描述>" \
  --out-dir <article-dir>/<week-slug> \
  --name-prefix <week-slug> \
  --count 6 \
  --response-format b64_json
```

### 4. HTML 兜底（最后手段）

仅在 Qwen 与 Seedream 都失败或不可用时使用：

```bash
python scripts/render_html_diagrams.py \
  --html <article-dir>/<week-slug>/<week-slug>_concept_diagrams.html \
  --out-dir <article-dir>/<week-slug>
```

### 5. 上传到 img.wemd.app

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
- `wemd_upload_cache.json`、生成图片、`__pycache__` 已在 `.gitignore` 中忽略。

## License

MIT
