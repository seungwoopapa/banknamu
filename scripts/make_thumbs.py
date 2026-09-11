#!/usr/bin/env python3
"""글마다 카드뉴스 형식의 섬네일 이미지를 만든다.

아카이브에 원본 이미지가 하나도 남아 있지 않아, 제목·카테고리·작성 시점을 담은
1200x630 카드 이미지를 대신 생성한다. 목록 카드 썸네일, 글 상단 헤더 이미지,
og:image 로 같은 파일을 쓴다.

macOS 기본 도구만 쓴다: qlmanage(SVG -> PNG 렌더), sips(크롭).
"""
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = json.load(open(ROOT / "config.json"))
POSTS = json.load(open(ROOT / "content" / "posts.json"))
OUT = ROOT / "docs" / "images" / "card"

W, H = 1200, 630          # 최종 카드 크기 (og:image 표준 비율)
PAD = 88                  # 좌우 여백
BAR = 16                  # 왼쪽 색 띠 두께

CAT_COLOR = {
    "deposit": "#1f7a4d", "insurance": "#1d5fa8", "tip": "#b5711a",
    "card": "#8a3fa0", "loan": "#b4443a", "invest": "#0f6e7a",
    "tax": "#4a5568", "bank": "#2f6f4f",
}
FONT = "-apple-system,'Apple SD Gothic Neo','Noto Sans KR',Helvetica,Arial,sans-serif"


def card_name(slug: str) -> str:
    return hashlib.md5(slug.encode()).hexdigest()[:10] + ".png"


def char_width(ch: str, size: float) -> float:
    """글자 하나가 차지하는 대략적인 가로 폭."""
    if ch == " ":
        return size * 0.30
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return size * 1.00
    if ch.isupper() or ch.isdigit():
        return size * 0.60
    return size * 0.52


def wrap(text: str, size: float, max_width: float, max_lines: int):
    """한글은 글자 단위로, 영문은 되도록 단어 단위로 줄을 나눈다."""
    lines, cur, cur_w = [], "", 0.0
    for ch in text:
        w = char_width(ch, size)
        if cur_w + w <= max_width:
            cur += ch
            cur_w += w
            continue
        # 줄이 넘칠 때: 영문/숫자 중간이면 마지막 공백에서 자른다
        if ch not in " " and re.match(r"[A-Za-z0-9]", ch) and " " in cur.rstrip():
            head, _, tail = cur.rstrip().rpartition(" ")
            lines.append(head)
            cur, cur_w = tail + ch, sum(char_width(c, size) for c in tail + ch)
        else:
            lines.append(cur.rstrip())
            cur, cur_w = ("" if ch == " " else ch), (0.0 if ch == " " else w)
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and cur.strip():
        lines.append(cur.strip())
    if len(lines) == max_lines:
        used = sum(len(x) for x in lines) + lines.count(" ")
        if used < len(text.replace(" ", "")) * 0.98 and len(lines[-1]) > 2:
            lines[-1] = lines[-1][:-1] + "…"
    return lines


def title_layout(title: str):
    """제목 길이에 맞춰 글자 크기와 줄 나눔을 정한다."""
    avail = W - PAD * 2 - BAR
    for size, max_lines in ((78, 3), (70, 3), (62, 4), (54, 4), (48, 5)):
        lines = wrap(title, size, avail, max_lines)
        if sum(char_width(c, size) for c in title) <= avail * max_lines * 0.97:
            return size, lines
    return 48, wrap(title, 48, avail, 5)


def kmonth(iso: str) -> str:
    y, m, _ = iso.split("-")
    return f"{y}년 {int(m)}월"


def svg_for(post) -> str:
    color = CAT_COLOR.get(post["category_slug"], CAT_COLOR["bank"])
    size, lines = title_layout(post["title"])
    x = PAD + BAR
    line_h = size * 1.30
    block_h = line_h * len(lines)
    # 제목 블록을 카드 가운데(브랜드/푸터 사이)에 놓는다
    top = 150 + (H - 150 - 120 - block_h) / 2 + size * 0.80
    tspans = "".join(
        f'<text x="{x}" y="{top + i * line_h:.0f}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="800" fill="#16212b" letter-spacing="-0.02em">{html.escape(l)}</text>'
        for i, l in enumerate(lines))
    cat = html.escape(post["category"])
    pill_w = len(post["category"]) * 30 + 56
    return f'''<rect width="{W}" height="{H}" fill="#fbfaf7"/>
<rect x="0" y="0" width="{BAR}" height="{H}" fill="{color}"/>
<rect x="{BAR}" y="0" width="{W - BAR}" height="6" fill="{color}" opacity="0.25"/>
<rect x="{x}" y="64" width="46" height="46" rx="11" fill="{color}"/>
<text x="{x + 23}" y="98" text-anchor="middle" font-family="{FONT}" font-size="28" font-weight="800" fill="#fff">B</text>
<text x="{x + 60}" y="98" font-family="{FONT}" font-size="30" font-weight="700" fill="#3b4652">{html.escape(CONF["site_name"])}</text>
<rect x="{W - PAD - pill_w}" y="64" width="{pill_w}" height="46" rx="23" fill="{color}" opacity="0.12"/>
<text x="{W - PAD - pill_w / 2}" y="96" text-anchor="middle" font-family="{FONT}" font-size="28" font-weight="700" fill="{color}">{cat}</text>
{tspans}
<rect x="{x}" y="{H - 108}" width="64" height="5" rx="2.5" fill="{color}"/>
<text x="{x}" y="{H - 56}" font-family="{FONT}" font-size="27" fill="#5f6b7a">{kmonth(post["published"])} 작성 · {CONF["domain"]}</text>'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    names = {}
    for p in POSTS:
        name = card_name(p["slug"])
        names[name] = p["title"]
        # qlmanage 는 정사각형으로 렌더하므로, 정사각 캔버스 가운데에 카드를 놓고 나중에 자른다
        body = svg_for(p)
        (tmp / (name[:-4] + ".svg")).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W}" viewBox="0 0 {W} {W}">'
            f'<rect width="{W}" height="{W}" fill="#fbfaf7"/>'
            f'<g transform="translate(0,{(W - H) // 2})">{body}</g></svg>', encoding="utf-8")
    svgs = sorted(str(f) for f in tmp.glob("*.svg"))
    subprocess.run(["qlmanage", "-t", "-s", str(W), "-o", str(tmp), *svgs],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    made = 0
    for name in names:
        src = tmp / (name[:-4] + ".svg.png")
        if not src.exists():
            print("  ! 렌더 실패:", names[name])
            continue
        subprocess.run(["sips", "-c", str(H), str(W), str(src), "--out", str(OUT / name)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        made += 1
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"cards: {made}/{len(POSTS)} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
