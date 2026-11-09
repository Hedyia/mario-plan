"""Aura Clinic CRM — Instagram renderer.

Usage:  python3 render.py posts.json OUT_DIR
posts.json = {"posts":[{"slug":"...","format":"feed"|"story","slides":[{...}]}]}
Each slide has a "type": cover | item | cta | single | chat | compare | story.
Outputs OUT_DIR/<slug>/NN.jpg (JPEG, as the Instagram API requires) + NN.png previews.
Needs: playwright (python) and Google Chrome or Chromium.
"""
import asyncio, html, json, os, shutil, sys
from playwright.async_api import async_playwright

TOOLS = os.path.dirname(os.path.abspath(__file__))
E = html.escape

FONT_FACES = "".join(
    f"@font-face{{font-family:'Plex';font-weight:{w};src:url('fonts/ibm-plex-sans-arabic-{sub}-{w}-normal.woff2') format('woff2');"
    f"unicode-range:{rng}}}"
    for w in (400, 500, 600, 700)
    for sub, rng in (("arabic", "U+0600-06FF,U+0750-077F,U+0870-088E,U+0890-0891,U+0898-08E1,U+08E3-08FF,U+200C-200E,U+2010-2011,U+204F,U+2E41,U+FB50-FDFF,U+FE70-FE74,U+FE76-FEFC"),
                     ("latin", "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2190-21FF,U+2212,U+2215,U+00D7,U+00F7"))
)

CSS = FONT_FACES + """
*{margin:0;padding:0;box-sizing:border-box}
:root{--navy:#0B1F4D;--blue:#1D4ED8;--sky:#0EA5E9;--cyan:#22D3EE;--bg:#F4F7FD;--muted:#4B5B7A;--line:#DCE5F5}
body{font-family:'Plex',sans-serif;direction:rtl;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.slide{position:relative;overflow:hidden}
.dark{background:linear-gradient(155deg,#0B1F4D 0%,#163A9E 55%,#0EA5E9 100%);color:#fff}
.light{background:var(--bg);color:var(--navy)}
.orb{position:absolute;border-radius:50%}
.brand{position:absolute;top:72px;right:80px;display:flex;align-items:center;gap:18px}
.brand .tile{width:78px;height:78px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(11,31,77,.18)}
.brand .tile img{width:62px;height:62px}
.brand .name{font-weight:700;font-size:30px;letter-spacing:.3px;direction:ltr}
.foot{position:absolute;bottom:64px;right:80px;left:80px;display:flex;justify-content:space-between;align-items:center;font-size:26px}
.count{direction:ltr;font-weight:600;letter-spacing:1px}
.chip{display:inline-block;background:rgba(34,211,238,.18);border:2px solid rgba(34,211,238,.6);color:#CFFAFE;font-weight:600;font-size:32px;padding:12px 30px;border-radius:999px}
.chip.l{background:#E3EEFF;border-color:#BBD3FF;color:var(--blue)}
.ltr{direction:ltr;unicode-bidi:isolate}
.hl{color:var(--cyan)}
.light .hl{color:var(--blue)}
.btn{display:inline-block;background:#fff;color:var(--navy);font-weight:700;font-size:44px;padding:30px 54px;border-radius:26px;box-shadow:0 20px 50px rgba(0,0,0,.18)}
.light .btn{background:linear-gradient(120deg,#1D4ED8,#0EA5E9);color:#fff;box-shadow:0 20px 50px rgba(29,78,216,.25)}
"""

def orbs(dark):
    if dark:
        return ('<div class="orb" style="width:720px;height:720px;left:-260px;bottom:-240px;background:radial-gradient(circle,rgba(34,211,238,.45),rgba(34,211,238,0) 70%)"></div>'
                '<div class="orb" style="width:520px;height:520px;right:-180px;top:-160px;background:radial-gradient(circle,rgba(255,255,255,.14),rgba(255,255,255,0) 70%)"></div>')
    return ('<div class="orb" style="width:640px;height:640px;left:-240px;top:-220px;background:radial-gradient(circle,rgba(14,165,233,.16),rgba(14,165,233,0) 70%)"></div>'
            '<div class="orb" style="width:560px;height:560px;right:-220px;bottom:-200px;background:radial-gradient(circle,rgba(29,78,216,.10),rgba(29,78,216,0) 70%)"></div>')

def brand(dark):
    c = "#fff" if dark else "var(--navy)"
    return f'<div class="brand"><div class="tile"><img src="mark.png"></div><div class="name" style="color:{c}">Aura Clinic CRM</div></div>'

def lines(ls, hl_first=False, hl_last=False):
    out = []
    for i, t in enumerate(ls):
        hl = (hl_first and i == 0) or (hl_last and i == len(ls) - 1)
        out.append(f'<span class="hl">{E(t)}</span>' if hl else E(t))
    return "<br>".join(out)

def foot(dark, left_html, idx, total):
    col = "#DCE8FF" if dark else "var(--muted)"
    cnt = f'<div class="count">{idx} / {total}</div>' if total > 1 else '<div></div>'
    return f'<div class="foot" style="color:{col}">{left_html}{cnt}</div>'

def dots(active, n):
    return '<div>' + "".join(
        f'<span style="display:inline-block;width:{56 if j==active else 18}px;height:18px;border-radius:9px;margin-left:10px;'
        f'background:{"linear-gradient(90deg,#1D4ED8,#22D3EE)" if j==active else ("#9DB4E8" if j<active else "#DCE5F5")}"></span>'
        for j in range(1, n + 1)) + '</div>'

def s_cover(s, i, n):
    size = s.get("title_size", 118)
    return True, f"""{orbs(True)}{brand(True)}
<div style="position:absolute;top:250px;right:80px;left:80px">
  <div class="chip">{E(s['kicker'])}</div>
  <div style="margin-top:56px;font-weight:700;font-size:{size}px;line-height:1.25;white-space:nowrap">{lines(s['title'], hl_first=s.get('hl','first')=='first', hl_last=s.get('hl')=='last')}</div>
  <div style="margin-top:36px;font-size:42px;line-height:1.6;color:#DCE8FF;max-width:880px">{E(s.get('sub',''))}</div>
</div>
{foot(True, '<div style="background:#fff;color:var(--navy);font-weight:700;font-size:30px;padding:16px 36px;border-radius:999px">اسحب ←</div>', i, n)}"""

def s_item(s, i, n):
    badge = s.get("badge", str(s.get("num", "")))
    small = len(badge) > 2
    badge_html = (f'<div style="width:{360 if small else 210}px;height:210px;border-radius:56px;background:linear-gradient(140deg,#1D4ED8,#22D3EE);'
                  f'display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:{96 if small else 130}px;'
                  f'box-shadow:0 24px 50px rgba(29,78,216,.28)" class="ltr">{E(badge)}</div>')
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:300px;right:80px;left:80px">
  {badge_html}
  <div style="margin-top:70px;font-weight:700;font-size:{s.get('title_size',92)}px;line-height:1.25;color:var(--navy)">{E(s['title'])}</div>
  <div style="margin-top:20px;width:120px;height:10px;border-radius:5px;background:linear-gradient(90deg,#22D3EE,#1D4ED8)"></div>
  <div style="margin-top:44px;font-size:46px;line-height:1.7;color:var(--muted);max-width:880px">{E(s['body'])}</div>
</div>
{foot(False, dots(s.get('dot', 1), s.get('dots', 1)), i, n)}"""

def s_cta(s, i, n):
    note = ""
    if s.get("note"):
        note = f'<div style="margin-top:36px;font-size:32px;color:#CFFAFE">{E(s["note"])}</div>'
    return True, f"""{orbs(True)}{brand(True)}
<div style="position:absolute;top:290px;right:80px;left:80px">
  <div style="font-weight:700;font-size:{s.get('title_size',88)}px;line-height:1.3">{lines(s['title'], hl_last=True)}</div>
  <div style="margin-top:48px;font-size:46px;line-height:1.7;color:#DCE8FF;max-width:900px">{s['body_html']}</div>
  {note}
  <div style="margin-top:80px" class="btn">ابعتلنا وهنرد على كل استفساراتك</div>
</div>
{foot(True, f'<div style="font-size:30px;font-weight:600">{E(s.get("footer",""))}</div>', i, n)}"""

def s_single(s, i, n):
    dark = s.get("theme", "dark") == "dark"
    parts = []
    for b in s["blocks"]:
        k = b["k"]
        if k == "text":
            col = "#DCE8FF" if dark else "var(--muted)"
            parts.append(f'<div style="margin-top:{b.get("mt",40)}px;font-size:{b.get("size",44)}px;line-height:1.65;color:{col};font-weight:{b.get("w",400)}">{b["html"]}</div>')
        elif k == "formula":
            rows = "".join(
                f'<div style="display:flex;align-items:center;gap:22px;margin-top:{0 if j==0 else 12}px">'
                f'<div style="width:64px;text-align:center;font-weight:700;font-size:50px;color:var(--sky)" class="ltr">{E(op)}</div>'
                f'<div style="font-size:42px;font-weight:{700 if j==len(b["rows"])-1 else 500};color:var(--navy)">{E(t)}</div></div>'
                for j, (op, t) in enumerate(b["rows"]))
            parts.append(f'<div style="margin-top:44px;background:#fff;border-radius:36px;padding:36px 48px;box-shadow:0 24px 60px rgba(0,0,0,.18)">{rows}</div>')
    return dark, f"""{orbs(dark)}{brand(dark)}
<div style="position:absolute;top:{s.get('top',230)}px;right:80px;left:80px" class="main">
  {f'<div class="chip{"" if dark else " l"}">{E(s["kicker"])}</div>' if s.get('kicker') else ''}
  <div style="margin-top:{48 if s.get('kicker') else 0}px;font-weight:700;font-size:{s.get('title_size',104)}px;line-height:1.25">{lines(s['title'], hl_last=True)}</div>
  {''.join(parts)}
</div>
{foot(dark, f'<div style="font-size:30px;font-weight:600">{E(s.get("footer",""))}</div>', i, n)}"""

def s_chat(s, i, n):
    bubbles = []
    for who, t in s["msgs"]:
        me = who == "r"  # receptionist = right (start side in RTL), blue
        bubbles.append(
            f'<div style="display:flex;justify-content:{"flex-start" if me else "flex-end"};margin-top:20px">'
            f'<div style="max-width:760px;font-size:38px;line-height:1.5;padding:22px 32px;border-radius:38px;'
            f'{"background:linear-gradient(120deg,#1D4ED8,#0EA5E9);color:#fff;border-top-right-radius:10px" if me else "background:#fff;color:var(--navy);border-top-left-radius:10px;box-shadow:0 10px 30px rgba(11,31,77,.08)"}">'
            f'<div style="font-size:26px;font-weight:600;opacity:.75;margin-bottom:4px">{E(s["names"][who])}</div>{E(t)}</div></div>')
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:200px;right:80px;left:80px" class="main">
  <div class="chip l">{E(s['kicker'])}</div>
  <div style="margin-top:22px">{''.join(bubbles)}</div>
  <div style="margin-top:40px;background:var(--navy);color:#fff;border-radius:32px;padding:30px 40px;font-size:36px;line-height:1.55">{s['punch_html']}</div>
</div>
{foot(False, f'<div style="font-size:30px;font-weight:600;color:var(--blue)">{E(s.get("footer",""))}</div>', i, n)}"""

def s_compare(s, i, n):
    def col(c, strong):
        items = "".join(f'<div style="display:flex;gap:16px;align-items:baseline;margin-top:14px;font-size:36px;line-height:1.4">'
                        f'<span style="flex:0 0 auto;width:16px;height:16px;border-radius:8px;margin-top:2px;background:{"#22D3EE" if strong else "#9DB4E8"}"></span>{E(x)}</div>' for x in c["items"])
        st = ("background:linear-gradient(150deg,#0B1F4D,#1D4ED8);color:#fff;box-shadow:0 24px 60px rgba(29,78,216,.30)" if strong
              else "background:#fff;color:var(--navy);box-shadow:0 10px 30px rgba(11,31,77,.08)")
        return (f'<div style="flex:1;border-radius:40px;padding:44px 40px;{st}">'
                f'<div style="font-size:30px;font-weight:600;opacity:.75">{E(c["label"])}</div>'
                f'<div style="font-size:46px;font-weight:700;margin-top:6px">{E(c["name"])}</div>{items}</div>')
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:220px;right:80px;left:80px" class="main">
  <div style="font-weight:700;font-size:{s.get('title_size',66)}px;line-height:1.3;white-space:nowrap">{lines(s['title'], hl_last=True)}</div>
  <div style="display:flex;gap:28px;margin-top:44px;align-items:stretch">{col(s['a'], False)}{col(s['b'], True)}</div>
  <div style="margin-top:36px;font-size:38px;line-height:1.6;color:var(--muted)">{s['bottom_html']}</div>
</div>
{foot(False, f'<div style="font-size:30px;font-weight:600;color:var(--blue)">{E(s.get("footer",""))}</div>', i, n)}"""

def s_story(s, i, n):
    opts = "".join(f'<div style="margin-top:26px;background:rgba(255,255,255,.12);border:2px solid rgba(255,255,255,.28);border-radius:30px;padding:30px 40px;font-size:46px;font-weight:600">{E(o)}</div>' for o in s["options"])
    return True, f"""{orbs(True)}
{brand(True).replace('class="brand"', 'class="brand" style="top:270px"', 1)}
<div style="position:absolute;top:470px;right:80px;left:80px">
  <div class="chip">{E(s['kicker'])}</div>
  <div style="margin-top:56px;font-weight:700;font-size:{s.get('title_size',100)}px;line-height:1.3">{lines(s['title'], hl_last=True)}</div>
  <div style="margin-top:40px">{opts}</div>
  <div style="margin-top:64px;font-size:40px;line-height:1.6;color:#DCE8FF">{E(s['ask'])}</div>
</div>"""

def s_storytip(s, i, n):
    return True, f"""{orbs(True)}
{brand(True).replace('class="brand"', 'class="brand" style="top:270px"', 1)}
<div style="position:absolute;top:500px;right:80px;left:80px">
  <div class="chip">{E(s['kicker'])}</div>
  <div style="margin-top:56px;font-weight:700;font-size:{s.get('title_size',92)}px;line-height:1.3">{lines(s['title'], hl_last=True)}</div>
  <div style="margin-top:48px;font-size:46px;line-height:1.65;color:#DCE8FF">{E(s['body'])}</div>
  <div style="margin-top:80px;display:inline-block;background:#fff;color:var(--navy);font-weight:700;font-size:40px;padding:26px 44px;border-radius:24px">تابع <span class="ltr">@auracliniccrm</span></div>
</div>"""

KINDS = {"storytip": s_storytip, "cover": s_cover, "item": s_item, "cta": s_cta, "single": s_single, "chat": s_chat, "compare": s_compare, "story": s_story}

def page(body, dark, w, h):
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{CSS}'
            f'html,body{{width:{w}px;height:{h}px}}.slide{{width:{w}px;height:{h}px}}</style></head>'
            f'<body><div class="slide {"dark" if dark else "light"}">{body}</div></body></html>')

async def main(spec_path, out_dir):
    spec = json.load(open(spec_path, encoding="utf-8"))
    from PIL import Image
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else await p.chromium.launch()
        for post in spec["posts"]:
            w, h = (1080, 1920) if post.get("format") == "story" else (1080, 1350)
            pg = await b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            d = os.path.join(out_dir, post["slug"]); os.makedirs(d, exist_ok=True)
            n = len(post["slides"])
            for i, s in enumerate(post["slides"], 1):
                dark, body = KINDS[s["type"]](s, i, n)
                f = os.path.join(TOOLS, f"_tmp_{post['slug']}_{i}.html")
                open(f, "w", encoding="utf-8").write(page(body, dark, w, h))
                await pg.goto("file://" + f); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(250)
                ok = await pg.evaluate("[...document.fonts].some(f=>f.family.includes('Plex') && f.status==='loaded')")
                collide = await pg.evaluate("(()=>{const m=document.querySelector('.main'),f=document.querySelector('.foot');if(!m||!f)return false;const mb=Math.max(...[...m.querySelectorAll('*')].map(e=>e.getBoundingClientRect().bottom));return mb>f.getBoundingClientRect().top-16})()")
                overflow = await pg.evaluate("[...document.querySelectorAll('.slide *:not(.orb)')].some(e=>{const r=e.getBoundingClientRect();return r.right>%d+1||r.left<-1||r.bottom>%d+1})" % (w, h))
                png = os.path.join(d, f"{i:02d}.png"); await pg.screenshot(path=png)
                Image.open(png).convert("RGB").save(os.path.join(d, f"{i:02d}.jpg"), "JPEG", quality=92, subsampling=0)
                os.remove(f)
                print(post["slug"], i, "font_ok" if ok else "FONT_MISSING", "OVERFLOW" if overflow else "", "COLLIDE" if collide else "")
            await pg.close()
        await b.close()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
