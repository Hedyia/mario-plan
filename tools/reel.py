"""Aura Clinic CRM — motion-graphic Reel renderer (1080x1920, 30fps, H.264 + silent AAC).

Usage: python3 reel.py reels.json OUT_DIR
reels.json = {"reels":[{"slug":"...","scenes":[{...}]}]}
Scene types: hook | chat | timeline | formula | punch | endcard  (each has "dur" in seconds)
Outputs OUT_DIR/<slug>/reel.mp4 and OUT_DIR/<slug>/cover.jpg
"""
import asyncio, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import CSS, E, lines, orbs, TOOLS  # noqa: E402
from playwright.async_api import async_playwright

W, H, FPS = 1080, 1920, 30

ANIM = """
@keyframes sin{from{opacity:0}to{opacity:1}}
@keyframes sout{from{opacity:1}to{opacity:0}}
@keyframes rise{from{opacity:0;transform:translateY(46px)}to{opacity:1;transform:none}}
@keyframes pop{0%{opacity:0;transform:scale(.86)}70%{opacity:1;transform:scale(1.03)}100%{opacity:1;transform:none}}
.scene{position:absolute;inset:0;overflow:hidden}
.scene>.inner{position:absolute;inset:0;overflow:hidden}
.a{animation-fill-mode:both}
"""

def rise(t, kind="rise", dur=0.55):
    return f'class="a" style="animation:{kind} {dur}s cubic-bezier(.2,.8,.2,1) {t:.2f}s both"'

def bg(dark):
    return ('<div style="position:absolute;inset:0;background:linear-gradient(160deg,#0B1F4D 0%,#163A9E 55%,#0EA5E9 100%)"></div>' if dark
            else '<div style="position:absolute;inset:0;background:#F4F7FD"></div>') + orbs(dark)

def head(dark, t):
    c = "#fff" if dark else "var(--navy)"
    return (f'<div {rise(t, "sin", .4)}><div style="position:absolute;top:170px;right:90px;display:flex;align-items:center;gap:18px">'
            f'<div style="width:80px;height:80px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(11,31,77,.18)"><img src="mark.png" style="width:64px;height:64px"></div>'
            f'<div style="font-weight:700;font-size:32px;direction:ltr;color:{c}">Aura Clinic CRM</div></div></div>')

def chip(text, t, dark=True):
    cls = "chip" if dark else "chip l"
    return f'<div {rise(t)}><div class="{cls}">{E(text)}</div></div>'

def sc_hook(s, t0):
    return True, f"""{head(True, t0)}
<div style="position:absolute;top:560px;right:90px;left:90px">
  {chip(s['kicker'], t0+.15) if s.get('kicker') else ''}
  <div {rise(t0+.45)}><div style="margin-top:60px;font-weight:700;font-size:{s.get('size',128)}px;line-height:1.22;color:#fff">{lines(s['title'][:-1])}</div></div>
  <div {rise(t0+1.0, 'pop', .6)}><div style="font-weight:700;font-size:{s.get('size',128)}px;line-height:1.22" class="hl">{E(s['title'][-1])}</div></div>
</div>"""

def sc_chat(s, t0):
    out = []
    for k, (who, txt) in enumerate(s["msgs"]):
        me = who == "r"
        st = ("background:linear-gradient(120deg,#1D4ED8,#0EA5E9);color:#fff;border-top-right-radius:12px" if me
              else "background:#fff;color:var(--navy);border-top-left-radius:12px;box-shadow:0 12px 34px rgba(11,31,77,.10)")
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
  <div {rise(t0+.1, 'pop', .5)}><div class="ltr" style="display:inline-flex;align-items:center;justify-content:center;height:220px;padding:0 60px;border-radius:60px;background:linear-gradient(140deg,#1D4ED8,#22D3EE);color:#fff;font-weight:700;font-size:110px;box-shadow:0 24px 50px rgba(29,78,216,.28)">{E(s['badge'])}</div></div>
  <div {rise(t0+.45)}><div style="margin-top:80px;font-weight:700;font-size:{s.get('size',100)}px;line-height:1.25;color:var(--navy)">{E(s['title'])}</div></div>
  <div {rise(t0+.85)}><div style="margin-top:40px;font-size:52px;line-height:1.6;color:var(--muted)">{E(s['body'])}</div></div>
</div>"""

def sc_formula(s, t0):
    rows = "".join(
        f'<div {rise(t0 + .5 + s["gap"]*j)}><div style="display:flex;align-items:center;gap:26px;margin-top:{0 if j==0 else 22}px">'
        f'<div class="ltr" style="width:70px;text-align:center;font-weight:700;font-size:64px;color:var(--sky)">{E(op)}</div>'
        f'<div style="font-size:54px;font-weight:{700 if j==len(s["rows"])-1 else 500};color:var(--navy)">{E(txt)}</div></div></div>'
        for j, (op, txt) in enumerate(s["rows"]))
    return False, f"""{head(False, t0)}
<div style="position:absolute;top:520px;right:90px;left:90px">
  {chip(s['kicker'], t0+.1, False)}
  <div style="margin-top:60px;background:#fff;border-radius:44px;padding:56px 56px;box-shadow:0 24px 60px rgba(11,31,77,.12)">{rows}</div>
</div>"""

def sc_punch(s, t0):
    return True, f"""{head(True, t0)}
<div style="position:absolute;top:560px;right:90px;left:90px">
  <div {rise(t0+.15)}><div style="font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3;color:#fff">{lines(s['title'][:-1])}</div></div>
  <div {rise(t0+.55)}><div style="font-weight:700;font-size:{s.get('size',96)}px;line-height:1.3" class="hl">{E(s['title'][-1])}</div></div>
  <div {rise(t0+1.1)}><div style="margin-top:56px;font-size:50px;line-height:1.65;color:#DCE8FF">{s['body_html']}</div></div>
</div>"""

def sc_endcard(s, t0):
    return True, f"""
<div style="position:absolute;top:470px;right:90px;left:90px;text-align:center">
  <div {rise(t0+.1, 'pop', .6)}><div style="display:inline-flex;width:230px;height:230px;border-radius:60px;background:#fff;align-items:center;justify-content:center;box-shadow:0 30px 70px rgba(0,0,0,.25)"><img src="mark.png" style="width:190px;height:190px"></div></div>
  <div {rise(t0+.4)}><div style="margin-top:44px;font-weight:700;font-size:48px;direction:ltr;color:#fff">Aura Clinic CRM</div></div>
  <div {rise(t0+.7)}><div style="margin-top:70px;font-weight:700;font-size:96px;line-height:1.3;color:#fff">تابع <span class="ltr hl">@auracliniccrm</span></div></div>
  <div {rise(t0+1.0)}><div style="margin-top:30px;font-size:50px;line-height:1.6;color:#DCE8FF">{E(s.get('sub','كل يوم حاجة تسهّل إدارة عيادتك'))}</div></div>
  <div {rise(t0+1.3)}><div style="margin-top:60px;display:inline-block;background:#fff;color:var(--navy);font-weight:700;font-size:42px;padding:28px 48px;border-radius:26px">ابعتلنا وهنرد على كل استفساراتك</div></div>
</div>"""

KINDS = {"hook": sc_hook, "chat": sc_chat, "timeline": sc_timeline, "formula": sc_formula, "punch": sc_punch, "endcard": sc_endcard}

def build(reel):
    t, parts = 0.0, []
    scenes = reel["scenes"]
    for k, s in enumerate(scenes):
        dark, inner = KINDS[s["type"]](s, t)
        fade_in = f"animation:sin .35s ease-out {t:.2f}s both" if k else ""
        fade_out = f"animation:sout .3s ease-in {t + s['dur'] - .3:.2f}s both" if k < len(scenes) - 1 else ""
        parts.append(f'<div class="scene a" style="{fade_in};z-index:{k}"><div class="inner a" style="{fade_out}">{bg(dark)}{inner}</div></div>')
        t += s["dur"]
    html = (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{CSS}{ANIM}'
            f'html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#0B1F4D;position:relative}}</style></head><body>{"".join(parts)}</body></html>')
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
                ms = i * 1000 / FPS
                await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={ms})")
                await pg.screenshot(path=os.path.join(frames, f"f{i:05d}.jpg"), type="jpeg", quality=92)
            cover_t = reel.get("cover_at", 2.0) * 1000
            await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={cover_t})")
            await pg.screenshot(path=os.path.join(d, "cover.jpg"), type="jpeg", quality=92)
            out = os.path.join(d, "reel.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.jpg"),
                            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                            "-r", str(FPS), "-g", "60", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)
            shutil.rmtree(frames); os.remove(f)
            print(reel["slug"], f"{total:.1f}s", n, "frames", os.path.getsize(out) // 1024, "KB")
        await b.close()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
