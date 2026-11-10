"""Aura Clinic CRM — motion-graphic Reel renderer (1080x1920, 30fps, H.264 + silent AAC).

Usage: python3 reel.py reels.json OUT_DIR
reels.json = {"reels":[{"slug":"...","theme":"blue|teal|coral|violet|charcoal|rose","cover_at":2.0,"scenes":[{...}]}]}
Scene types (each has "dur" seconds): hook | quote | chat | timeline | formula | receipt | punch | endcard
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

ANIM = """
@keyframes sin{from{opacity:0}to{opacity:1}}
@keyframes sout{from{opacity:1}to{opacity:0}}
@keyframes rise{from{opacity:0;transform:translateY(46px)}to{opacity:1;transform:none}}
@keyframes pop{0%{opacity:0;transform:scale(.86)}70%{opacity:1;transform:scale(1.03)}100%{opacity:1;transform:none}}
@keyframes strike{from{width:0}to{width:100%}}
.scene{position:absolute;inset:0;overflow:hidden}
.scene>.inner{position:absolute;inset:0;overflow:hidden}
"""

def rise(t, kind="rise", dur=0.55):
    return f'style="animation:{kind} {dur}s cubic-bezier(.2,.8,.2,1) {t:.2f}s both"'

def bg(dark):
    return ('<div style="position:absolute;inset:0;background:linear-gradient(160deg,var(--g1) 0%,var(--g2) 55%,var(--g3) 100%)"></div>' if dark
            else '<div style="position:absolute;inset:0;background:var(--bgL)"></div>') + orbs(dark)

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

KINDS = {"storycard": sc_storycard, "hook": sc_hook, "quote": sc_quote, "chat": sc_chat, "timeline": sc_timeline, "formula": sc_formula,
         "receipt": sc_receipt, "punch": sc_punch, "endcard": sc_endcard}

def build(reel):
    t, parts = 0.0, []
    scenes = reel["scenes"]
    for k, s in enumerate(scenes):
        dark, inner = KINDS[s["type"]](s, t)
        th = theme_vars(s.get("theme", reel.get("theme", "blue")))
        fade_in = f"animation:sin .35s ease-out {t:.2f}s both;" if k else ""
        fade_out = f"animation:sout .3s ease-in {t + s['dur'] - .3:.2f}s both;" if k < len(scenes) - 1 else ""
        parts.append(f'<div class="scene {"dark" if dark else "light"}" style="{fade_in}z-index:{k};{th}"><div class="inner" style="{fade_out}">{bg(dark)}{inner}</div></div>')
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
                await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={i * 1000 / FPS})")
                await pg.screenshot(path=os.path.join(frames, f"f{i:05d}.jpg"), type="jpeg", quality=92)
            await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={reel.get('cover_at', 2.0) * 1000})")
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
