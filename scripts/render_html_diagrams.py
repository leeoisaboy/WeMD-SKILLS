"""Render .diagram sections from an HTML file into transparent PNGs."""
import argparse
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

DEFAULT_CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def pick_browser(custom):
    if custom and Path(custom).exists():
        return custom
    for candidate in (DEFAULT_CHROME, DEFAULT_EDGE):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("Chrome/Edge not found, pass --chrome")


def check_layout(page, diagram_id):
    return page.evaluate(
        """(id) => {
          const root = document.getElementById(id);
          if (!root) {
            return { issues: [`missing root ${id}`], info: [] };
          }
          const rootRect = root.getBoundingClientRect();
          const nodes = [...root.querySelectorAll(".node, .panel-title, .diagram-title, .diagram-subtitle")];
          const issues = [];
          const info = [];
          for (const el of nodes) {
            if (!el) {
              continue;
            }
            const r = el.getBoundingClientRect();
            const text = (el.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 40);
            const overflowX = el.scrollWidth - el.clientWidth;
            const overflowY = el.scrollHeight - el.clientHeight;
            info.push({
              id: el.id || el.className,
              text,
              left: Math.round(r.left - rootRect.left),
              top: Math.round(r.top - rootRect.top),
              right: Math.round(r.right - rootRect.left),
              bottom: Math.round(r.bottom - rootRect.top),
              overflowX,
              overflowY
            });
            if (overflowX > 1 || overflowY > 1) {
              issues.push(`overflow ${id || el.className}: ${text} (${overflowX}x${overflowY})`);
            }
            if (r.left < rootRect.left - 1 || r.top < rootRect.top - 1 ||
                r.right > rootRect.right + 1 || r.bottom > rootRect.bottom + 1) {
              issues.push(`out-of-bounds ${id || el.className}: ${text}`);
            }
          }
          return { issues, info };
        }""",
        diagram_id,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, help="HTML file containing section.diagram elements")
    parser.add_argument("--out-dir", default=None, help="PNG output directory (default: HTML folder)")
    parser.add_argument("--chrome", default=None, help="Chrome/Edge executable path")
    parser.add_argument("--scale", type=float, default=2.0, help="pixel scale for output PNGs")
    args = parser.parse_args()

    html = Path(args.html).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else html.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=pick_browser(args.chrome),
            headless=True,
        )
        page = browser.new_page(
            viewport={"width": 1600, "height": 1200},
            device_scale_factor=int(args.scale),
        )
        page.goto(html.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")

        for section in page.locator("section.diagram").all():
            diagram_id = section.get_attribute("id")
            output = section.get_attribute("data-output") or f"{diagram_id}.png"
            out = out_dir / output
            section.screenshot(path=str(out), omit_background=True)

            image = Image.open(out)
            corner_alpha = image.getpixel((2, 2))[-1]
            layout = check_layout(page, diagram_id)
            print(f"{diagram_id} -> {out.name} ({image.size[0]}x{image.size[1]}, alpha={corner_alpha})")
            if layout["issues"]:
                print("  layout issues:")
                for issue in layout["issues"]:
                    print(f"   - {issue}")

        browser.close()


if __name__ == "__main__":
    main()
