"""Aura Clinic CRM — motion-graphic Reel renderer (1080x1920, 30fps, H.264 + silent AAC).

Usage: python3 reel.py reels.json OUT_DIR
reels.json = {"reels":[{"slug":"...","theme":"blue|teal|coral|violet|charcoal|rose","cover_at":2.0,"scenes":[{...}]}]}
Scene types (each has "dur" seconds): hook | quote | chat | timeline | formula | receipt | punch | endcard | storycard
  + kinetic (text-only slam typography) | pov (situational opener with emoji) | checklist (tasks get ✕ or ✓)
  | split (before/after panels) | phone (illustrative lock screen with notifications) | counter (number counts up)
  Each new scene's docstring shows its JSON. Optional per scene "bg": paper | solid | grid (default gradient/light) and "theme".
Outputs OUT_DIR/<slug>/reel.mp4 (with original background music, loudness-normalised) and OUT_DIR/<slug>/cover.jpg
Optional per reel: "music": calm_piano | warm_pad | soft_lofi | bright_soft (default chosen from the theme), "music_seed": int
Safe area: keep text between y=300 and y=1450 (Instagram UI covers the top bar and the caption area).
"""
import asyncio, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import CSS, E, lines, orbs, TOOLS, theme_vars  # noqa: E402
from music import make_track  # noqa: E402

# Every reel/story gets original calm music (never silent). Override per reel with "music": preset, "music_seed": int.
THEME_MUSIC = {"blue": "calm_piano", "teal": "warm_pad", "coral": "soft_lofi", "violet": "bright_soft", "charcoal": "warm_pad", "rose": "calm_piano"}
from playwright.async_api import async_playwright

W, H, FPS = 1080, 1920, 30
# wait two animation frames after seeking so every tile is re-rastered (avoids stale rectangles on moving elements)
RAF2 = "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"

ANIM = """
@keyframes sin{from{opacity:0}to{opacity:1}}
@keyframes sout{from{opacity:1}to{opacity:0}}
@keyframes rise{from{opacity:0;transform:translateY(46px)}to{opacity:1;transform:none}}
@keyframes pop{0%{opacity:0;transform:scale(.86)}70%{opacity:1;transform:scale(1.03)}100%{opacity:1;transform:none}}
@keyframes strike{from{width:0}to{width:100%}}
@keyframes slam{0%{opacity:0;transform:scale(1.45)}55%{opacity:1;transform:scale(.97)}100%{opacity:1;transform:none}}
@keyframes mark{from{background-size:0% 100%}to{background-size:100% 100%}}
@keyframes wob{0%,100%{transform:rotate(-7deg) scale(1)}50%{transform:rotate(7deg) scale(1.06)}}
@keyframes up{from{opacity:0;transform:translateY(420px)}to{opacity:1;transform:none}}
@keyframes slidein{from{opacity:0;transform:translateY(-60px) scale(.96)}to{opacity:1;transform:none}}
@keyframes shake{0%,100%{transform:none}20%{transform:translateX(-14px)}40%{transform:translateX(12px)}60%{transform:translateX(-8px)}80%{transform:translateX(5px)}}
.scene{position:absolute;inset:0;overflow:hidden}
.scene>.inner{position:absolute;inset:0;overflow:hidden}
.emo{font-family:'Noto Color Emoji','Apple Color Emoji',sans-serif;line-height:1}
.mk{background-image:linear-gradient(var(--mk),var(--mk));background-repeat:no-repeat;background-position:right center;padding:0 18px;border-radius:14px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
"""

def rise(t, kind="rise", dur=0.55):
    return f'style="animation:{kind} {dur}s cubic-bezier(.2,.8,.2,1) {t:.2f}s both"'

def bg(dark, style=None):
    """Background per scene. style (optional, from the scene's "bg"): paper | solid | grid; default = gradient (dark) / light."""
    if style == "paper":   # warm notebook paper with ruled lines and a margin line
        return ('<div style="position:absolute;inset:0;background:#FBF6EC;background-image:repeating-linear-gradient(0deg,transparent 0 78px,rgba(30,41,59,.07) 78px 80px)"></div>'
                '<div style="position:absolute;top:0;bottom:0;right:60px;width:4px;background:rgba(225,29,72,.25)"></div>')
    if style == "solid":   # flat brand colour with big soft shapes
        return ('<div style="position:absolute;inset:0;background:var(--b1)"></div>'
                '<div class="orb" style="width:900px;height:900px;left:-420px;bottom:-380px;background:var(--b2);opacity:.28"></div>'
                '<div style="position:absolute;width:380px;height:380px;right:-120px;top:120px;border-radius:90px;transform:rotate(18deg);background:rgba(255,255,255,.08)"></div>')
    if style == "grid":    # light dotted grid
        return ('<div style="position:absolute;inset:0;background:var(--bgL);background-image:radial-gradient(color-mix(in srgb,var(--b1) 22%,transparent) 3px,transparent 3.5px);background-size:54px 54px"></div>')
    return ('<div style="position:absolute;inset:0;background:linear-gradient(160deg,var(--g1) 0%,var(--g2) 55%,var(--g3) 100%)"></div>' if dark
            else '<div style="position:absolute;inset:0;background:var(--bgL)"></div>') + orbs(dark)

def is_dark(s, default):
    st = s.get("bg")
    return {"paper": False, "grid": False, "solid": True}.get(st, default)

def head(dark, t):
    c = "#fff" if dark else "var(--ink)"
    return (f'<div {rise(t, "sin", .4)}><div style="position:absolute;top:170px;right:90px;display:flex;align-items:center;gap:18px">'
            f'<div style="width:80px;height:80px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(0,0,0,.18)"><img src="mark.png" style="width:64px;height:64px"></div>'
            f'<div style="font-weight:700;font-size:32px;direction:ltr;color:{c}">Aura Clinic CRM</div></div></div>')

def chip(text, t, dark=True):
    return f'<div {rise(t)}><div class="{"chip" if dark else "chip l"}">{E(text)}</div></div>'

def sc_hook(s, t0):
    sz = s.get('size', 128)
    return True, f"""{head(True, t0)}
<div style="position:absolute;top:560px;right:90px;left:90px">
  {chip(s['kicker'], t0+.15) if s.get('kicker') else ''}
  <div {rise(t0+.45)}><div style="margin-top:60px;font-weight:700;font-size:{sz}px;line-height:1.22;color:#fff">{lines(s['title'][:-1])}</div></div>
  <div {rise(t0+1.0, 'pop', .6)}><div style="font-weight:700;font-size:{sz}px;line-height:1.22" class="hl">{E(s['title'][-1])}</div></div>
</div>"""

def sc_quote(s, t0):
    return False, f"""{head(False, t0)}
<div style="position:absolute;top:520px;right:90px;left:90px">
  {chip(s['label'], t0+.1, False)}
  <div {rise(t0+.4, 'pop', .6)}><div style="margin-top:80px;position:relative;background:#fff;border-radius:52px;padding:110px 70px 80px;box-shadow:0 30px 70px rgba(0,0,0,.10)">
    <div style="position:absolute;top:-56px;right:60px;width:130px;height:130px;border-radius:50%;background:linear-gradient(140deg,var(--b1),var(--b2));color:#fff;font-size:150px;font-weight:700;line-height:195px;text-align:center">”</div>
    <div style="font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3;color:var(--ink)">{E(s['quote'])}</div>
  </div></div>
  <div {rise(t0+1.3)}><div style="margin-top:56px;font-size:54px;line-height:1.5;color:var(--muted)">{E(s.get('reaction',''))}</div></div>
</div>"""

def sc_chat(s, t0):
    out = []
    for k, (who, txt) in enumerate(s["msgs"]):
        me = who == "r"
        st = ("background:linear-gradient(120deg,var(--b1),var(--b2));color:#fff;border-top-right-radius:12px" if me
              else "background:#fff;color:var(--ink);border-top-left-radius:12px;box-shadow:0 12px 34px rgba(0,0,0,.10)")
        out.append(f'<div {rise(t0 + s["gap"]*k + .35, "pop", .5)}><div style="display:flex;justify-content:{"flex-start" if me else "flex-end"};margin-top:30px">'
                   f'<div style="max-width:800px;font-size:48px;line-height:1.45;padding:28px 40px;border-radius:44px;{st}">'
                   f'<div style="font-size:28px;font-weight:600;opacity:.75;margin-bottom:6px">{E(s["names"][who])}</div>{E(txt)}</div></div></div>')
    return False, f"""{head(False, t0)}
<div style="position:absolute;top:400px;right:90px;left:90px">
  {chip(s['kicker'], t0+.1, False)}
  <div style="margin-top:20px">{''.join(out)}</div>
</div>"""

def sc_timeline(s, t0):
    return False, f"""{head(False, t0)}
<div style="position:absolute;top:560px;right:90px;left:90px">
  <div {rise(t0+.1, 'pop', .5)}><div class="ltr" style="display:inline-flex;align-items:center;justify-content:center;height:220px;padding:0 60px;border-radius:60px;background:linear-gradient(140deg,var(--b1),var(--b2));color:#fff;font-weight:700;font-size:110px;box-shadow:0 24px 50px rgba(0,0,0,.18)">{E(s['badge'])}</div></div>
  <div {rise(t0+.45)}><div style="margin-top:80px;font-weight:700;font-size:{s.get('size',100)}px;line-height:1.25;color:var(--ink)">{E(s['title'])}</div></div>
  <div {rise(t0+.85)}><div style="margin-top:40px;font-size:52px;line-height:1.6;color:var(--muted)">{E(s['body'])}</div></div>
</div>"""

def sc_formula(s, t0):
    rows = "".join(
        f'<div {rise(t0 + .5 + s["gap"]*j)}><div style="display:flex;align-items:center;gap:26px;margin-top:{0 if j==0 else 22}px">'
        f'<div class="ltr" style="width:70px;text-align:center;font-weight:700;font-size:64px;color:var(--b1)">{E(op)}</div>'
        f'<div style="font-size:54px;font-weight:{700 if j==len(s["rows"])-1 else 500};color:var(--ink)">{E(txt)}</div></div></div>'
        for j, (op, txt) in enumerate(s["rows"]))
    return False, f"""{head(False, t0)}
<div style="position:absolute;top:520px;right:90px;left:90px">
  {chip(s['kicker'], t0+.1, False)}
  <div style="margin-top:60px;background:#fff;border-radius:44px;padding:56px;box-shadow:0 24px 60px rgba(0,0,0,.10)">{rows}</div>
</div>"""

def sc_receipt(s, t0):
    rows = "".join(
        f'<div {rise(t0 + .7 + s["gap"]*j)}><div style="display:flex;align-items:baseline;gap:16px;font-size:50px;margin-top:26px;color:#1F2937">'
        f'<span>{E(a)}</span><span style="flex:1;border-bottom:5px dotted #CBD5E1;transform:translateY(-12px)"></span><span class="ltr" style="font-weight:600">{E(b)}</span></div></div>'
        for j, (a, b) in enumerate(s["rows"]))
    tt = t0 + .7 + s["gap"] * len(s["rows"]) + .2
    zig = "polygon(" + ",".join(f"{x}% {100 if k % 2 == 0 else 97.5}%" for k, x in enumerate(range(100, -1, -4))) + ",0 0,100% 0)"
    return True, f"""{head(True, t0)}
<div style="position:absolute;top:440px;right:90px;left:90px">
  <div {rise(t0+.1)}><div style="font-weight:700;font-size:{s.get('size',88)}px;line-height:1.25;color:#fff">{lines(s['title'], hl_last=True)}</div></div>
  <div {rise(t0+.4, 'pop', .6)}><div style="margin:60px 20px 0;background:#FFFEF7;border-radius:20px 20px 0 0;padding:56px 60px 100px;clip-path:{zig};box-shadow:0 30px 60px rgba(0,0,0,.3)">
    <div style="text-align:center;font-weight:700;font-size:46px;color:#111827">{E(s.get('receipt_title','فاتورة'))}</div>
    <div style="margin-top:16px;border-top:5px dashed #CBD5E1"></div>
    {rows}
    <div style="margin-top:40px;border-top:5px dashed #CBD5E1"></div>
    <div {rise(tt, 'pop', .6)}><div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:30px;font-size:56px;font-weight:700;color:var(--accL)"><span>{E(s['total'][0])}</span><span class="ltr">{E(s['total'][1])}</span></div></div>
  </div></div>
</div>"""

def sc_punch(s, t0):
    return True, f"""{head(True, t0)}
<div style="position:absolute;top:560px;right:90px;left:90px">
  <div {rise(t0+.15)}><div style="font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3;color:#fff">{lines(s['title'][:-1])}</div></div>
  <div {rise(t0+.55)}><div style="font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3" class="hl">{E(s['title'][-1])}</div></div>
  <div {rise(t0+1.1)}><div style="margin-top:56px;font-size:50px;line-height:1.65;color:rgba(255,255,255,.9)">{s['body_html']}</div></div>
</div>"""

def sc_endcard(s, t0):
    return True, f"""
<div style="position:absolute;top:470px;right:90px;left:90px;text-align:center">
  <div {rise(t0+.1, 'pop', .6)}><div style="display:inline-flex;width:230px;height:230px;border-radius:60px;background:#fff;align-items:center;justify-content:center;box-shadow:0 30px 70px rgba(0,0,0,.25)"><img src="mark.png" style="width:190px;height:190px"></div></div>
  <div {rise(t0+.4)}><div style="margin-top:44px;font-weight:700;font-size:48px;direction:ltr;color:#fff">Aura Clinic CRM</div></div>
  <div {rise(t0+.7)}><div style="margin-top:70px;font-weight:700;font-size:96px;line-height:1.3;color:#fff">تابع <span class="ltr hl">@auracliniccrm</span></div></div>
  <div {rise(t0+1.0)}><div style="margin-top:30px;font-size:50px;line-height:1.6;color:rgba(255,255,255,.9)">{E(s.get('sub','كل يوم حاجة تسهّل إدارة عيادتك'))}</div></div>
  <div {rise(t0+1.3)}><div style="margin-top:60px;display:inline-block;background:#fff;color:var(--ink);font-weight:700;font-size:42px;padding:28px 48px;border-radius:26px">ابعتلنا وهنرد على كل استفساراتك</div></div>
</div>"""

def sc_storycard(s, t0):
    """Animated story (one scene, 7-9 s): chip, title, then body or options one by one, then follow button."""
    k = t0 + 1.4
    body = ""
    if s.get("options"):
        for j, o in enumerate(s["options"]):
            body += (f'<div {rise(k + .6*j, "pop", .5)}><div style="margin-top:26px;background:rgba(255,255,255,.14);border:2px solid rgba(255,255,255,.32);'
                     f'border-radius:30px;padding:30px 40px;font-size:48px;font-weight:600;color:#fff">{E(o)}</div></div>')
        k += .6 * len(s["options"])
    if s.get("body"):
        body += f'<div {rise(k)}><div style="margin-top:44px;font-size:48px;line-height:1.65;color:rgba(255,255,255,.92)">{E(s["body"])}</div></div>'
        k += .6
    if s.get("ask"):
        body += f'<div {rise(k)}><div style="margin-top:50px;font-size:42px;line-height:1.6;color:rgba(255,255,255,.9)">{E(s["ask"])}</div></div>'
        k += .5
    follow = (f'<div {rise(k + .3, "pop", .5)}><div style="margin-top:70px;display:inline-block;background:#fff;color:var(--ink);font-weight:700;'
              f'font-size:42px;padding:26px 46px;border-radius:24px">تابع <span class="ltr">@auracliniccrm</span></div></div>') if s.get("follow", True) else ""
    return True, f"""
<div {rise(t0, "sin", .4)}><div style="position:absolute;top:270px;right:80px;display:flex;align-items:center;gap:18px">
  <div style="width:78px;height:78px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center"><img src="mark.png" style="width:62px;height:62px"></div>
  <div style="font-weight:700;font-size:30px;direction:ltr;color:#fff">Aura Clinic CRM</div></div></div>
<div style="position:absolute;top:470px;right:80px;left:80px">
  {chip(s['kicker'], t0 + .2)}
  <div {rise(t0 + .5)}><div style="margin-top:56px;font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3;color:#fff">{lines(s['title'][:-1])}</div></div>
  <div {rise(t0 + .9, 'pop', .6)}><div style="font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3" class="hl">{E(s['title'][-1])}</div></div>
  {body}{follow}
</div>"""

ICON = {
    "ok": '<svg viewBox="0 0 24 24" width="{w}" height="{w}"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="{c}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "no": '<svg viewBox="0 0 24 24" width="{w}" height="{w}"><path d="M7 7l10 10M17 7L7 17" fill="none" stroke="{c}" stroke-width="3.2" stroke-linecap="round"/></svg>',
}

def icon(kind, w=48, c="#fff"):
    return ICON[kind].format(w=w, c=c)

def sc_kinetic(s, t0):
    """Text-only kinetic typography: lines slam in one by one (beat s), line index "hl" gets a marker sweep.
    {"type":"kinetic","dur":4.5,"bg":"solid|paper|grid","kicker":"..."?,"lines":["..",".."],"hl":1,"size":118,"beat":.5,"sub":"..."?}"""
    dark = is_dark(s, True)
    sz, beat = s.get("size", 118), s.get("beat", .5)
    ink = "#fff" if dark else "var(--ink)"
    mk = "var(--acc)" if dark else "color-mix(in srgb,var(--b2) 50%,transparent)"
    out = []
    for k, ln in enumerate(s["lines"]):
        t = t0 + .25 + beat * k
        inner = (f'<span class="mk" style="--mk:{mk};color:{"var(--g1)" if dark else "var(--ink)"};animation:mark .45s ease-out {t + .35:.2f}s both">{E(ln)}</span>'
                 if k == s.get("hl", -1) else E(ln))
        out.append(f'<div {rise(t, "slam", .45)}><div style="font-weight:700;font-size:{sz}px;line-height:1.32;color:{ink};margin-top:{12 if k else 0}px">{inner}</div></div>')
    kick = chip(s["kicker"], t0 + .1, dark) if s.get("kicker") else ""
    t_sub = t0 + .25 + beat * len(s["lines"]) + .25
    sub = (f'<div {rise(t_sub)}><div style="margin-top:56px;font-size:50px;line-height:1.6;color:{"rgba(255,255,255,.9)" if dark else "var(--muted)"}">{E(s["sub"])}</div></div>'
           if s.get("sub") else "")
    return dark, f"""{head(dark, t0)}
<div style="position:absolute;top:360px;bottom:470px;right:90px;left:90px;display:flex;flex-direction:column;justify-content:center">
  {kick}<div style="margin-top:{44 if kick else 0}px">{''.join(out)}</div>{sub}
</div>"""

def sc_pov(s, t0):
    """Situational opener: a tilted "POV:" sticker, a 2-line situation and a big wobbling emoji.
    {"type":"pov","dur":3.4,"bg":"paper|grid|solid"?,"title":["الموقف","تكملته"],"emoji":"😅","size":92}"""
    dark = is_dark(s, False)
    ink = "#fff" if dark else "var(--ink)"
    sz = s.get("size", 92)
    return dark, f"""{head(dark, t0)}
<div style="position:absolute;top:450px;right:90px;left:90px">
  <div {rise(t0 + .1, 'pop', .5)}><div class="ltr" style="display:inline-block;transform:rotate(-5deg);background:#111827;color:#fff;font-weight:700;font-size:100px;padding:4px 44px 16px;border-radius:24px;box-shadow:12px 12px 0 var(--b2)">POV:</div></div>
  <div {rise(t0 + .45)}><div style="margin-top:76px;font-weight:700;font-size:{sz}px;line-height:1.3;color:{ink}">{lines(s['title'][:1])}</div></div>
  <div {rise(t0 + .8)}><div style="font-weight:700;font-size:{sz}px;line-height:1.3" class="hl">{lines(s['title'][1:])}</div></div>
  <div {rise(t0 + 1.15, 'pop', .5)}><div style="margin-top:64px;text-align:center"><span class="emo" style="display:inline-block;font-size:250px;animation:wob 1.6s ease-in-out {t0 + 1.6:.2f}s infinite">{E(s.get('emoji', '😅'))}</span></div></div>
</div>"""

def sc_checklist(s, t0):
    """Task cards that get a red ✕ (mode "fail", the card shakes) or a green ✓ (mode "ok"), each with an optional reaction line.
    {"type":"checklist","dur":6,"bg":"paper"?,"kicker":"..","title":".."?,"mode":"fail|ok","gap":1.5,"items":[{"t":"المهمة","r":"اللي حصل","e":"🫠"}]}  (max 3 items with reactions, 4 without)"""
    dark = is_dark(s, False)
    ok = s.get("mode", "fail") == "ok"
    gap = s.get("gap", 1.5)
    rows = []
    for k, it in enumerate(s["items"]):
        t = t0 + .55 + gap * k
        react = (f'<div {rise(t + .8)}><div style="margin-top:10px;font-size:42px;line-height:1.5;color:var(--muted)">{E(it["r"])} '
                 f'<span class="emo" style="font-size:44px;vertical-align:-4px">{E(it.get("e", ""))}</span></div></div>') if it.get("r") else ""
        shake = "" if ok else f"animation:shake .45s ease {t + .6:.2f}s both;"
        rows.append(f'<div {rise(t)}><div style="{shake}display:flex;gap:30px;align-items:flex-start;background:#fff;border-radius:36px;padding:32px 36px;'
                    f'margin-top:{0 if k == 0 else 24}px;box-shadow:0 16px 40px rgba(0,0,0,.08)">'
                    f'<div style="flex:none;position:relative;width:76px;height:76px;border-radius:22px;border:5px solid #CBD5E1;margin-top:2px">'
                    f'<div style="position:absolute;inset:-5px;border-radius:22px;background:{"#16A34A" if ok else "#DC2626"};display:flex;align-items:center;justify-content:center;'
                    f'animation:pop .4s cubic-bezier(.2,.8,.2,1) {t + .55:.2f}s both">{icon("ok" if ok else "no", 54)}</div></div>'
                    f'<div style="flex:1"><div style="font-size:50px;font-weight:600;line-height:1.4;color:var(--ink)">{E(it["t"])}</div>{react}</div></div></div>')
    title = (f'<div {rise(t0 + .3)}><div style="margin-top:34px;font-weight:700;font-size:{s.get("size", 76)}px;line-height:1.3;color:{"#fff" if dark else "var(--ink)"}">{E(s["title"])}</div></div>'
             if s.get("title") else "")
    return dark, f"""{head(dark, t0)}
<div style="position:absolute;top:400px;right:90px;left:90px">
  {chip(s['kicker'], t0 + .1, dark) if s.get('kicker') else ''}{title}
  <div style="margin-top:50px">{''.join(rows)}</div>
</div>"""

def sc_split(s, t0):
    """Before/after split screen: panel "a" (paper, crossed items) on top, panel "b" (brand colour, ticked items) below; rows appear in pairs.
    {"type":"split","dur":7.5,"title":"..","a":{"label":"بالورق","items":[3 short lines]},"b":{"label":"بسيستم واحد","items":[3 short lines]},"gap":1.3}"""
    gap = s.get("gap", 1.3)
    def rows(items, start, good):
        out = []
        for k, txt in enumerate(items):
            t = start + gap * k
            ic = (f'<div style="flex:none;width:58px;height:58px;border-radius:50%;background:{"rgba(255,255,255,.95)" if good else "#FEE2E2"};display:flex;align-items:center;justify-content:center">'
                  f'{icon("ok" if good else "no", 40, "var(--b1)" if good else "#DC2626")}</div>')
            out.append(f'<div {rise(t, "pop", .45)}><div style="display:flex;align-items:center;gap:24px;margin-top:{0 if k == 0 else 22}px">{ic}'
                       f'<div style="font-size:46px;line-height:1.35;font-weight:{600 if good else 500};color:{"#fff" if good else "#334155"}">{E(txt)}</div></div></div>')
        return "".join(out)
    a, b = s["a"], s["b"]
    return False, f"""{head(False, t0)}
<div style="position:absolute;top:300px;right:90px;left:90px">
  <div {rise(t0 + .1)}><div style="font-weight:700;font-size:{s.get('size', 74)}px;line-height:1.25;color:var(--ink)">{E(s['title'])}</div></div>
  <div {rise(t0 + .35)}><div style="margin-top:40px;background:#FFFDF7;border:3px dashed #CBD5E1;border-radius:40px;padding:40px 44px;transform:rotate(-1deg)">
    <div style="display:inline-block;background:#E2E8F0;color:#334155;font-weight:700;font-size:36px;padding:8px 26px;border-radius:999px;margin-bottom:30px">{E(a['label'])}</div>
    {rows(a['items'], t0 + .7, False)}</div></div>
  <div {rise(t0 + .6)}><div style="margin-top:34px;background:linear-gradient(135deg,var(--b1),var(--b2));border-radius:40px;padding:40px 44px;box-shadow:0 24px 50px rgba(0,0,0,.18)">
    <div style="display:inline-block;background:rgba(255,255,255,.2);color:#fff;font-weight:700;font-size:36px;padding:8px 26px;border-radius:999px;margin-bottom:30px">{E(b['label'])}</div>
    {rows(b['items'], t0 + .7 + gap / 2, True)}</div></div>
</div>"""

def sc_phone(s, t0):
    """Illustrative phone lock screen rising from the bottom; notifications slide in one by one (generic icons, no app UI claims).
    {"type":"phone","dur":6.5,"bg":"solid"?,"kicker":".."?,"title":["..",".."],"clock":"9:41","date":"..","gap":1.1,"notifs":[{"e":"📅","app":"..","t":"..","w":"دلوقتي"}]}"""
    dark = is_dark(s, True)
    gap = s.get("gap", 1.1)
    notifs = "".join(
        f'<div {rise(t0 + 1.6 + gap * k, "slidein", .5)}><div style="display:flex;gap:20px;align-items:flex-start;background:rgba(255,255,255,.9);border-radius:34px;padding:22px 26px;margin-top:{0 if k == 0 else 16}px;box-shadow:0 10px 30px rgba(0,0,0,.18)">'
        f'<div style="flex:none;width:66px;height:66px;border-radius:18px;background:#fff;display:flex;align-items:center;justify-content:center"><span class="emo" style="font-size:42px">{E(n.get("e", "💬"))}</span></div>'
        f'<div style="flex:1;min-width:0"><div style="display:flex;justify-content:space-between;font-size:25px;color:#475569"><b style="color:#0F172A">{E(n["app"])}</b><span>{E(n.get("w", "دلوقتي"))}</span></div>'
        f'<div style="font-size:30px;line-height:1.45;color:#0F172A;margin-top:4px">{E(n["t"])}</div></div></div></div>'
        for k, n in enumerate(s["notifs"]))
    ink = "#fff" if dark else "var(--ink)"
    return dark, f"""{head(dark, t0)}
<div style="position:absolute;top:330px;right:90px;left:90px">
  {chip(s['kicker'], t0 + .1, dark) if s.get('kicker') else ''}
  <div {rise(t0 + .25)}><div style="margin-top:{30 if s.get('kicker') else 0}px;font-weight:700;font-size:{s.get('size', 76)}px;line-height:1.28;color:{ink}">{lines(s['title'], hl_last=True)}</div></div>
</div>
<div style="position:absolute;left:140px;width:800px;top:{s.get('phone_top', 690)}px;height:1500px;animation:up .8s cubic-bezier(.2,.8,.2,1) {t0 + .5:.2f}s both">
  <div style="position:absolute;inset:0;border-radius:96px;background:#0B0B0F;box-shadow:0 40px 90px rgba(0,0,0,.35)"></div>
  <div style="position:absolute;inset:22px;border-radius:76px;clip-path:inset(0 round 76px);background:linear-gradient(170deg,var(--g1),var(--g2) 60%,var(--g3))">
    <div style="position:absolute;top:22px;left:50%;transform:translateX(-50%);width:190px;height:52px;border-radius:30px;background:#000"></div>
    <div style="position:absolute;top:84px;left:0;right:0;text-align:center;color:#fff">
      <div style="font-size:30px;opacity:.85">{E(s.get('date', ''))}</div>
      <div class="ltr" style="font-size:120px;font-weight:600;line-height:1.1">{E(s.get('clock', '9:41'))}</div></div>
    <div style="position:absolute;top:250px;left:26px;right:26px">{notifs}</div>
  </div>
</div>"""

def sc_counter(s, t0):
    """Big number that counts up from 0, with a unit line and a short body.
    {"type":"counter","dur":4,"bg":"solid|paper"?,"kicker":"..","to":26,"unit":"..","body":".."?}"""
    dark = is_dark(s, True)
    n = int(s["to"]); nm = f"cn{n}x{int(t0 * 100)}"
    ink = "#fff" if dark else "var(--ink)"
    return dark, f"""<style>@property --{nm}{{syntax:'<integer>';inherits:false;initial-value:0}}
@keyframes {nm}{{from{{--{nm}:0}}to{{--{nm}:{n}}}}}
.{nm}{{counter-reset:c var(--{nm});animation:{nm} 1.5s cubic-bezier(.2,.8,.2,1) {t0 + .55:.2f}s both}}.{nm}::after{{content:counter(c)}}</style>
{head(dark, t0)}
<div style="position:absolute;top:470px;right:90px;left:90px">
  {chip(s['kicker'], t0 + .1, dark) if s.get('kicker') else ''}
  <div {rise(t0 + .35, 'pop', .5)}><div class="ltr {nm} hl" style="margin-top:30px;text-align:right;font-weight:700;font-size:{s.get('num_size', 340)}px;line-height:1.05"></div></div>
  <div {rise(t0 + .9)}><div style="font-weight:700;font-size:{s.get('size', 76)}px;line-height:1.3;color:{ink}">{E(s['unit'])}</div></div>
  <div {rise(t0 + 1.4)}><div style="margin-top:44px;font-size:50px;line-height:1.6;color:{"rgba(255,255,255,.9)" if dark else "var(--muted)"}">{E(s.get('body', ''))}</div></div>
</div>"""

KINDS = {"storycard": sc_storycard, "hook": sc_hook, "quote": sc_quote, "chat": sc_chat, "timeline": sc_timeline, "formula": sc_formula,
         "receipt": sc_receipt, "punch": sc_punch, "endcard": sc_endcard,
         "kinetic": sc_kinetic, "pov": sc_pov, "checklist": sc_checklist, "split": sc_split, "phone": sc_phone, "counter": sc_counter}

def build(reel):
    t, parts = 0.0, []
    scenes = reel["scenes"]
    for k, s in enumerate(scenes):
        dark, inner = KINDS[s["type"]](s, t)
        th = theme_vars(s.get("theme", reel.get("theme", "blue")))
        fade_in = f"animation:sin .35s ease-out {t:.2f}s both;" if k else ""
        fade_out = f"animation:sout .3s ease-in {t + s['dur'] - .3:.2f}s both;" if k < len(scenes) - 1 else ""
        parts.append(f'<div class="scene {"dark" if dark else "light"}" style="{fade_in}z-index:{k};{th}"><div class="inner" style="{fade_out}">{bg(dark, s.get("bg"))}{inner}</div></div>')
        t += s["dur"]
    html = (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{CSS}{ANIM}'
            f'html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#000;position:relative}}</style></head><body>{"".join(parts)}</body></html>')
    return html, t

async def main(spec_path, out_dir):
    spec = json.load(open(spec_path, encoding="utf-8"))
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else await p.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for reel in spec["reels"]:
            html, total = build(reel)
            d = os.path.join(out_dir, reel["slug"]); os.makedirs(d, exist_ok=True)
            f = os.path.join(TOOLS, f"_tmp_reel_{reel['slug']}.html")
            open(f, "w", encoding="utf-8").write(html)
            await pg.goto("file://" + f); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getAnimations().forEach(a=>a.pause())")
            frames = tempfile.mkdtemp(prefix="frames_")
            n = int(round(total * FPS))
            for i in range(n):
                await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={i * 1000 / FPS})"); await pg.evaluate(RAF2)
                await pg.screenshot(path=os.path.join(frames, f"f{i:05d}.jpg"), type="jpeg", quality=92)
            await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={reel.get('cover_at', 2.0) * 1000})"); await pg.evaluate(RAF2)
            await pg.screenshot(path=os.path.join(d, "cover.jpg"), type="jpeg", quality=92)
            out = os.path.join(d, "reel.mp4")
            preset = reel.get("music", THEME_MUSIC.get(reel.get("theme", "blue"), "calm_piano"))
            seed = reel.get("music_seed", sum(map(ord, reel["slug"])) % 1000)
            wav = make_track(preset, total, os.path.join(frames, "music.wav"), seed)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.jpg"),
                            "-i", wav, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000", "-shortest",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                            "-r", str(FPS), "-g", "60", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)
            shutil.rmtree(frames); os.remove(f)
            print(reel["slug"], reel.get("theme", "blue"), preset, f"{total:.1f}s", n, "frames", os.path.getsize(out) // 1024, "KB")
        await b.close()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
