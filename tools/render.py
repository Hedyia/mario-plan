"""Aura Clinic CRM — Instagram renderer (feed 1080x1350, story 1080x1920).

Usage:  python3 render.py posts.json OUT_DIR
posts.json = {"posts":[{"slug":"...","format":"feed"|"story","theme":"blue|teal|coral|violet|charcoal|rose","slides":[{...}]}]}
A slide may override "theme". Slide types:
  cover | item | sticky | cta | single | quote | receipt | calendar | chat | compare | story | storytip
Outputs OUT_DIR/<slug>/NN.jpg (JPEG for the Instagram API) + NN.png previews.
Rotate themes and layouts between posts so the grid never looks the same twice in a row.
"""
import asyncio, html, json, os, shutil, sys
from playwright.async_api import async_playwright

TOOLS = os.path.dirname(os.path.abspath(__file__))
E = html.escape

THEMES = {
    #          g1         g2         g3        acc(dark)  bgL        ink        muted      accL       b1         b2        chipT
    "blue":    ("#0B1F4D", "#163A9E", "#0EA5E9", "#22D3EE", "#F4F7FD", "#0B1F4D", "#4B5B7A", "#1D4ED8", "#1D4ED8", "#22D3EE", "#CFFAFE"),
    "teal":    ("#042F2E", "#0F766E", "#14B8A6", "#FDE68A", "#ECFDF8", "#042F2E", "#3F5F5C", "#0F766E", "#0F766E", "#2DD4BF", "#CCFBF1"),
    "coral":   ("#431407", "#C2410C", "#FB923C", "#FEF3C7", "#FFF7ED", "#431407", "#7C5A4A", "#EA580C", "#EA580C", "#FDBA74", "#FFEDD5"),
    "violet":  ("#1E1B4B", "#5B21B6", "#A78BFA", "#F5D0FE", "#F5F3FF", "#1E1B4B", "#5B5675", "#6D28D9", "#6D28D9", "#C4B5FD", "#EDE9FE"),
    "charcoal":("#0A0A0A", "#1F2937", "#374151", "#FACC15", "#FAFAF3", "#111827", "#4B5563", "#A16207", "#111827", "#4B5563", "#FEF9C3"),
    "rose":    ("#4C0519", "#BE123C", "#FB7185", "#FFE4E6", "#FFF1F2", "#4C0519", "#7A4B55", "#E11D48", "#E11D48", "#FDA4AF", "#FFE4E6"),
}

def theme_vars(name):
    g1, g2, g3, acc, bgl, ink, muted, accl, b1, b2, chipt = THEMES[name]
    return (f"--g1:{g1};--g2:{g2};--g3:{g3};--acc:{acc};--bgL:{bgl};--ink:{ink};--muted:{muted};"
            f"--accL:{accl};--b1:{b1};--b2:{b2};--chipT:{chipt}")

FONT_FACES = "".join(
    f"@font-face{{font-family:'Plex';font-weight:{w};src:url('fonts/ibm-plex-sans-arabic-{sub}-{w}-normal.woff2') format('woff2');"
    f"unicode-range:{rng}}}"
    for w in (400, 500, 600, 700)
    for sub, rng in (("arabic", "U+0600-06FF,U+0750-077F,U+0870-088E,U+0890-0891,U+0898-08E1,U+08E3-08FF,U+200C-200E,U+2010-2011,U+204F,U+2E41,U+FB50-FDFF,U+FE70-FE74,U+FE76-FEFC"),
                     ("latin", "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2190-21FF,U+2212,U+2215,U+00D7,U+00F7"))
)

CSS = FONT_FACES + """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Plex',sans-serif;direction:rtl;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.slide{position:relative;overflow:hidden}
.dark{background:linear-gradient(155deg,var(--g1) 0%,var(--g2) 55%,var(--g3) 100%);color:#fff}
.light{background:var(--bgL);color:var(--ink)}
.orb{position:absolute;border-radius:50%}
.brand{position:absolute;top:72px;right:80px;display:flex;align-items:center;gap:18px}
.brand .tile{width:78px;height:78px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(0,0,0,.16)}
.brand .tile img{width:62px;height:62px}
.brand .name{font-weight:700;font-size:30px;letter-spacing:.3px;direction:ltr}
.foot{position:absolute;bottom:64px;right:80px;left:80px;display:flex;justify-content:space-between;align-items:center;font-size:26px}
.count{direction:ltr;font-weight:600;letter-spacing:1px}
.chip{display:inline-block;background:rgba(255,255,255,.14);border:2px solid rgba(255,255,255,.35);color:var(--chipT);font-weight:600;font-size:32px;padding:12px 30px;border-radius:999px}
.chip.l{background:#fff;border-color:transparent;color:var(--accL);box-shadow:0 6px 20px rgba(0,0,0,.06)}
.ltr{direction:ltr;unicode-bidi:isolate}
.hl{color:var(--acc)}
.light .hl{color:var(--accL)}
.btn{display:inline-block;background:#fff;color:var(--ink);font-weight:700;font-size:44px;padding:30px 54px;border-radius:26px;box-shadow:0 20px 50px rgba(0,0,0,.18)}
.dots i{display:inline-block;height:18px;border-radius:9px;margin-left:10px}
"""

def orbs(dark):
    if dark:
        return ('<div class="orb" style="width:720px;height:720px;left:-260px;bottom:-240px;background:radial-gradient(circle,rgba(255,255,255,.18),rgba(255,255,255,0) 70%)"></div>'
                '<div class="orb" style="width:520px;height:520px;right:-180px;top:-160px;background:radial-gradient(circle,rgba(255,255,255,.12),rgba(255,255,255,0) 70%)"></div>')
    return ('<div class="orb" style="width:640px;height:640px;left:-240px;top:-220px;background:radial-gradient(circle,color-mix(in srgb,var(--b2) 28%,transparent),transparent 70%)"></div>'
            '<div class="orb" style="width:560px;height:560px;right:-220px;bottom:-200px;background:radial-gradient(circle,color-mix(in srgb,var(--b1) 16%,transparent),transparent 70%)"></div>')

def brand(dark, top=72):
    c = "#fff" if dark else "var(--ink)"
    return f'<div class="brand" style="top:{top}px"><div class="tile"><img src="mark.png"></div><div class="name" style="color:{c}">Aura Clinic CRM</div></div>'

def lines(ls, hl_first=False, hl_last=False):
    out = []
    for i, t in enumerate(ls):
        hl = (hl_first and i == 0) or (hl_last and i == len(ls) - 1)
        out.append(f'<span class="hl">{E(t)}</span>' if hl else E(t))
    return "<br>".join(out)

def foot(dark, left_html, idx, total):
    col = "rgba(255,255,255,.85)" if dark else "var(--muted)"
    cnt = f'<div class="count">{idx} / {total}</div>' if total > 1 else '<div></div>'
    return f'<div class="foot" style="color:{col}">{left_html}{cnt}</div>'

def dots(active, n):
    return '<div class="dots">' + "".join(
        f'<i style="width:{56 if j==active else 18}px;background:{"linear-gradient(90deg,var(--b1),var(--b2))" if j==active else ("color-mix(in srgb,var(--b1) 45%,white)" if j<active else "color-mix(in srgb,var(--b1) 14%,white)")}"></i>'
        for j in range(1, n + 1)) + '</div>'

def swipe():
    return '<div style="background:#fff;color:var(--ink);font-weight:700;font-size:30px;padding:16px 36px;border-radius:999px;box-shadow:0 8px 20px rgba(0,0,0,.08)">اسحب ←</div>'

def text_foot(s, dark):
    col = "#fff" if dark else "var(--accL)"
    return f'<div style="font-size:30px;font-weight:600;color:{col}">{E(s.get("footer",""))}</div>'

# ---------- slide types ----------
def s_cover(s, i, n):
    size = s.get("title_size", 118)
    return True, f"""{orbs(True)}{brand(True)}
<div style="position:absolute;top:250px;right:80px;left:80px" class="main">
  <div class="chip">{E(s['kicker'])}</div>
  <div style="margin-top:56px;font-weight:700;font-size:{size}px;line-height:1.25;white-space:nowrap">{lines(s['title'], hl_first=s.get('hl','first')=='first', hl_last=s.get('hl')=='last')}</div>
  <div style="margin-top:36px;font-size:42px;line-height:1.6;color:rgba(255,255,255,.88);max-width:880px">{E(s.get('sub',''))}</div>
</div>
{foot(True, swipe(), i, n)}"""

def badge(s):
    txt = s.get("badge", str(s.get("num", "")))
    shape = s.get("shape", "square")
    wide = len(txt) > 2
    w = 360 if wide else 210
    rad = "56px" if wide else {"square": "56px", "circle": "50%", "pill": "999px"}[shape]
    return (f'<div class="ltr" style="width:{w}px;height:210px;border-radius:{rad};background:linear-gradient(140deg,var(--b1),var(--b2));'
            f'display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:{96 if wide else 130}px;'
            f'box-shadow:0 24px 50px color-mix(in srgb,var(--b1) 35%,transparent)">{E(txt)}</div>')

def s_item(s, i, n):
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:300px;right:80px;left:80px" class="main">
  {badge(s)}
  <div style="margin-top:70px;font-weight:700;font-size:{s.get('title_size',92)}px;line-height:1.25;color:var(--ink)">{E(s['title'])}</div>
  <div style="margin-top:20px;width:120px;height:10px;border-radius:5px;background:linear-gradient(90deg,var(--b2),var(--b1))"></div>
  <div style="margin-top:44px;font-size:46px;line-height:1.7;color:var(--muted);max-width:880px">{E(s['body'])}</div>
</div>
{foot(False, dots(s.get('dot', 1), s.get('dots', 1)), i, n)}"""

def s_sticky(s, i, n):
    note = s.get("note", "#FEF08A")
    rot = s.get("rot", -2.5)
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:280px;right:110px;left:110px" class="main">
  <div style="position:relative;transform:rotate({rot}deg);background:{note};border-radius:10px 10px 40px 10px;padding:90px 70px 80px;box-shadow:0 30px 60px rgba(0,0,0,.14),0 2px 0 rgba(0,0,0,.04)">
    <div style="position:absolute;top:-26px;right:50%;transform:translateX(50%) rotate(3deg);width:220px;height:56px;background:rgba(255,255,255,.65);border-radius:6px;box-shadow:0 4px 10px rgba(0,0,0,.08)"></div>
    <div class="ltr" style="font-weight:700;font-size:120px;line-height:1;color:var(--accL);text-align:right">{E(str(s.get('num','')))}</div>
    <div style="margin-top:36px;font-weight:700;font-size:{s.get('title_size',80)}px;line-height:1.25;color:#1F2937">{E(s['title'])}</div>
    <div style="margin-top:34px;font-size:44px;line-height:1.65;color:#374151">{E(s['body'])}</div>
  </div>
</div>
{foot(False, dots(s.get('dot', 1), s.get('dots', 1)), i, n)}"""

def s_cta(s, i, n):
    return True, f"""{orbs(True)}{brand(True)}
<div style="position:absolute;top:290px;right:80px;left:80px" class="main">
  <div style="font-weight:700;font-size:{s.get('title_size',88)}px;line-height:1.3">{lines(s['title'], hl_last=True)}</div>
  <div style="margin-top:48px;font-size:46px;line-height:1.7;color:rgba(255,255,255,.9);max-width:900px">{s['body_html']}</div>
  <div style="margin-top:80px" class="btn">ابعتلنا وهنرد على كل استفساراتك</div>
</div>
{foot(True, text_foot(s, True), i, n)}"""

def s_single(s, i, n):
    dark = s.get("dark", True)
    parts = []
    for b in s["blocks"]:
        if b["k"] == "text":
            col = "rgba(255,255,255,.9)" if dark else "var(--muted)"
            parts.append(f'<div style="margin-top:{b.get("mt",40)}px;font-size:{b.get("size",44)}px;line-height:1.65;color:{col};font-weight:{b.get("w",400)}">{b["html"]}</div>')
    return dark, f"""{orbs(dark)}{brand(dark)}
<div style="position:absolute;top:{s.get('top',260)}px;right:80px;left:80px" class="main">
  {f'<div class="chip{"" if dark else " l"}">{E(s["kicker"])}</div>' if s.get('kicker') else ''}
  <div style="margin-top:{48 if s.get('kicker') else 0}px;font-weight:700;font-size:{s.get('title_size',104)}px;line-height:1.25">{lines(s['title'], hl_last=True)}</div>
  {''.join(parts)}
</div>
{foot(dark, text_foot(s, dark), i, n)}"""

def s_quote(s, i, n):
    """Situational card: 'لما المريض يقولك…'."""
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:250px;right:80px;left:80px" class="main">
  <div class="chip l">{E(s['label'])}</div>
  <div style="margin-top:70px;position:relative;background:#fff;border-radius:48px;padding:90px 64px 70px;box-shadow:0 24px 60px rgba(0,0,0,.08)">
    <div style="position:absolute;top:-46px;right:56px;width:110px;height:110px;border-radius:50%;background:linear-gradient(140deg,var(--b1),var(--b2));color:#fff;font-size:130px;font-weight:700;line-height:165px;text-align:center">”</div>
    <div style="font-weight:700;font-size:{s.get('size',86)}px;line-height:1.3;color:var(--ink)">{E(s['quote'])}</div>
  </div>
  <div style="margin-top:46px;font-size:46px;line-height:1.6;color:var(--muted)">{s['reaction_html']}</div>
</div>
{foot(False, text_foot(s, False), i, n)}"""

def s_receipt(s, i, n):
    rows = "".join(
        f'<div style="display:flex;align-items:baseline;gap:16px;font-size:42px;margin-top:22px;color:#1F2937">'
        f'<span>{E(a)}</span><span style="flex:1;border-bottom:4px dotted #CBD5E1;transform:translateY(-10px)"></span><span class="ltr" style="font-weight:600">{E(b)}</span></div>'
        for a, b in s["rows"])
    zig = "polygon(" + ",".join(f"{x}% {100 if k % 2 == 0 else 97}%" for k, x in enumerate(range(100, -1, -4))) + ",0 0,100% 0)"
    return True, f"""{orbs(True)}{brand(True)}
<div style="position:absolute;top:220px;right:80px;left:80px" class="main">
  <div style="font-weight:700;font-size:{s.get('title_size',84)}px;line-height:1.25">{lines(s['title'], hl_last=True)}</div>
  <div style="margin:48px 30px 0;background:#FFFEF7;border-radius:18px 18px 0 0;padding:46px 56px 80px;clip-path:{zig};box-shadow:0 30px 60px rgba(0,0,0,.25)">
    <div style="text-align:center;font-weight:700;font-size:40px;color:#111827;letter-spacing:1px">{E(s.get('receipt_title','فاتورة'))}</div>
    <div style="margin-top:14px;border-top:4px dashed #CBD5E1"></div>
    {rows}
    <div style="margin-top:34px;border-top:4px dashed #CBD5E1"></div>
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:26px;font-size:48px;font-weight:700;color:var(--accL)"><span>{E(s['total'][0])}</span><span class="ltr">{E(s['total'][1])}</span></div>
  </div>
  <div style="margin-top:40px;font-size:40px;line-height:1.6;color:rgba(255,255,255,.92)">{s.get('note_html','')}</div>
</div>
{foot(True, text_foot(s, True), i, n)}"""

def s_calendar(s, i, n):
    cells = []
    for d, slots in s["days"]:
        items = "".join(
            f'<div style="margin-top:12px;border-radius:14px;padding:10px 4px;font-size:24px;font-weight:600;text-align:center;'
            + ("background:#FEE2E2;color:#B91C1C;text-decoration:line-through" if st == "x" else "background:color-mix(in srgb,var(--b2) 24%,white);color:var(--ink)")
            + f'">{E(t)}</div>' for t, st in slots)
        cells.append(f'<div style="flex:1;background:#fff;border-radius:22px;padding:16px 8px 18px;box-shadow:0 8px 24px rgba(0,0,0,.06)">'
                     f'<div style="text-align:center;font-weight:700;font-size:26px;color:var(--muted)">{E(d)}</div>{items}</div>')
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:210px;right:70px;left:70px" class="main">
  <div class="chip l">{E(s['kicker'])}</div>
  <div style="margin-top:34px;font-weight:700;font-size:{s.get('title_size',100)}px;line-height:1.22;color:var(--ink);white-space:nowrap">{lines(s['title'], hl_first=True)}</div>
  <div style="display:flex;gap:12px;margin-top:44px">{''.join(cells)}</div>
  <div style="margin-top:28px;font-size:34px;color:var(--muted)">{E(s.get('sub',''))}</div>
</div>
{foot(False, swipe(), i, n)}"""

def s_chat(s, i, n):
    bubbles = []
    for who, t in s["msgs"]:
        me = who == "r"
        bubbles.append(
            f'<div style="display:flex;justify-content:{"flex-start" if me else "flex-end"};margin-top:20px">'
            f'<div style="max-width:760px;font-size:38px;line-height:1.5;padding:22px 32px;border-radius:38px;'
            f'{"background:linear-gradient(120deg,var(--b1),var(--b2));color:#fff;border-top-right-radius:10px" if me else "background:#fff;color:var(--ink);border-top-left-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.08)"}">'
            f'<div style="font-size:24px;font-weight:600;opacity:.75;margin-bottom:4px">{E(s["names"][who])}</div>{E(t)}</div></div>')
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:200px;right:80px;left:80px" class="main">
  <div class="chip l">{E(s['kicker'])}</div>
  <div style="margin-top:22px">{''.join(bubbles)}</div>
  <div style="margin-top:40px;background:var(--ink);color:#fff;border-radius:32px;padding:30px 40px;font-size:36px;line-height:1.55">{s['punch_html']}</div>
</div>
{foot(False, text_foot(s, False), i, n)}"""

def s_compare(s, i, n):
    def col(c, strong):
        items = "".join(f'<div style="display:flex;gap:16px;align-items:baseline;margin-top:14px;font-size:36px;line-height:1.4">'
                        f'<span style="flex:0 0 auto;width:16px;height:16px;border-radius:8px;margin-top:2px;background:{"var(--acc)" if strong else "color-mix(in srgb,var(--ink) 30%,white)"}"></span>{E(x)}</div>' for x in c["items"])
        st = ("background:linear-gradient(150deg,var(--g1),var(--g2));color:#fff;box-shadow:0 24px 60px rgba(0,0,0,.22)" if strong
              else "background:#fff;color:var(--ink);box-shadow:0 10px 30px rgba(0,0,0,.06)")
        return (f'<div style="flex:1;border-radius:40px;padding:44px 40px;{st}">'
                f'<div style="font-size:30px;font-weight:600;opacity:.75">{E(c["label"])}</div>'
                f'<div style="font-size:46px;font-weight:700;margin-top:6px">{E(c["name"])}</div>{items}</div>')
    return False, f"""{orbs(False)}{brand(False)}
<div style="position:absolute;top:220px;right:80px;left:80px" class="main">
  <div style="font-weight:700;font-size:{s.get('title_size',66)}px;line-height:1.3;white-space:nowrap">{lines(s['title'], hl_last=True)}</div>
  <div style="display:flex;gap:28px;margin-top:44px;align-items:stretch">{col(s['a'], False)}{col(s['b'], True)}</div>
  <div style="margin-top:36px;font-size:38px;line-height:1.6;color:var(--muted)">{s['bottom_html']}</div>
</div>
{foot(False, text_foot(s, False), i, n)}"""

def follow_btn(dark_bg):
    st = "background:#fff;color:var(--ink)" if dark_bg else "background:var(--ink);color:#fff"
    return f'<div style="margin-top:80px;display:inline-block;{st};font-weight:700;font-size:40px;padding:26px 44px;border-radius:24px">تابع <span class="ltr">@auracliniccrm</span></div>'

def s_story(s, i, n):
    opts = "".join(f'<div style="margin-top:26px;background:rgba(255,255,255,.14);border:2px solid rgba(255,255,255,.32);border-radius:30px;padding:30px 40px;font-size:46px;font-weight:600">{E(o)}</div>' for o in s["options"])
    return True, f"""{orbs(True)}{brand(True, 270)}
<div style="position:absolute;top:470px;right:80px;left:80px">
  <div class="chip">{E(s['kicker'])}</div>
  <div style="margin-top:56px;font-weight:700;font-size:{s.get('title_size',100)}px;line-height:1.3">{lines(s['title'], hl_last=True)}</div>
  <div style="margin-top:40px">{opts}</div>
  <div style="margin-top:64px;font-size:40px;line-height:1.6;color:rgba(255,255,255,.9)">{E(s['ask'])}</div>
</div>"""

def s_storytip(s, i, n):
    if s.get("style") == "sticky":
        return False, f"""{orbs(False)}{brand(False, 270)}
<div style="position:absolute;top:470px;right:100px;left:100px">
  <div class="chip l">{E(s['kicker'])}</div>
  <div style="margin-top:60px;transform:rotate(-2deg);background:{s.get('note','#FEF08A')};border-radius:10px 10px 46px 10px;padding:90px 66px 84px;box-shadow:0 30px 60px rgba(0,0,0,.14)">
    <div style="font-weight:700;font-size:{s.get('title_size',84)}px;line-height:1.3;color:#1F2937">{lines(s['title'])}</div>
    <div style="margin-top:40px;font-size:46px;line-height:1.65;color:#374151">{E(s['body'])}</div>
  </div>
  {follow_btn(False)}
</div>"""
    return True, f"""{orbs(True)}{brand(True, 270)}
<div style="position:absolute;top:500px;right:80px;left:80px">
  <div class="chip">{E(s['kicker'])}</div>
  <div style="margin-top:56px;font-weight:700;font-size:{s.get('title_size',92)}px;line-height:1.3">{lines(s['title'], hl_last=True)}</div>
  <div style="margin-top:48px;font-size:46px;line-height:1.65;color:rgba(255,255,255,.9)">{E(s['body'])}</div>
  {follow_btn(True)}
</div>"""

KINDS = {"cover": s_cover, "item": s_item, "sticky": s_sticky, "cta": s_cta, "single": s_single, "quote": s_quote,
         "receipt": s_receipt, "calendar": s_calendar, "chat": s_chat, "compare": s_compare, "story": s_story, "storytip": s_storytip}

def page(body, dark, w, h, theme):
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{CSS}'
            f'html,body{{width:{w}px;height:{h}px}}.slide{{width:{w}px;height:{h}px}}</style></head>'
            f'<body><div class="slide {"dark" if dark else "light"}" style="{theme_vars(theme)}">{body}</div></body></html>')

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
                theme = s.get("theme", post.get("theme", "blue"))
                f = os.path.join(TOOLS, f"_tmp_{post['slug']}_{i}.html")
                open(f, "w", encoding="utf-8").write(page(body, dark, w, h, theme))
                await pg.goto("file://" + f); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(250)
                ok = await pg.evaluate("[...document.fonts].some(f=>f.family.includes('Plex') && f.status==='loaded')")
                collide = await pg.evaluate("(()=>{const m=document.querySelector('.main'),f=document.querySelector('.foot');if(!m||!f)return false;const mb=Math.max(...[...m.querySelectorAll('*')].map(e=>e.getBoundingClientRect().bottom));return mb>f.getBoundingClientRect().top-16})()")
                overflow = await pg.evaluate("[...document.querySelectorAll('.slide *:not(.orb)')].some(e=>{const r=e.getBoundingClientRect();return r.right>%d+1||r.left<-1||r.bottom>%d+1})" % (w, h))
                png = os.path.join(d, f"{i:02d}.png"); await pg.screenshot(path=png)
                Image.open(png).convert("RGB").save(os.path.join(d, f"{i:02d}.jpg"), "JPEG", quality=92, subsampling=0)
                os.remove(f)
                print(post["slug"], i, theme, "font_ok" if ok else "FONT_MISSING", "OVERFLOW" if overflow else "", "COLLIDE" if collide else "")
            await pg.close()
        await b.close()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
