"""Edit a real (team-filmed) video into an Aura reel.

Usage: python3 edit_real.py INPUT_VIDEO OUT_DIR --hook "سطر 1|سطر 2" [--max 45] [--fit auto|crop|frame] [--theme blue]
- crop (default for vertical clips): crops/scales to 1080x1920 (9:16), 30fps, keeps the original sound,
  shows the hook text in a banner for the first 3.5 s and a small logo the whole time
- frame (default for horizontal clips, e.g. a laptop screen recording of Aura with TEST data): the whole video sits
  inside a device frame on a branded background; the hook stays on screen as the title the whole time
- appends the 2.8 s Aura end card ("تابع @auracliniccrm") with music
- a clip without sound gets original calm music (never silent)
Outputs OUT_DIR/reel.mp4 and OUT_DIR/cover.jpg
"""
import argparse, asyncio, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import CSS, E, TOOLS, theme_vars  # noqa: E402
from music import make_track  # noqa: E402
from playwright.async_api import async_playwright

def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)

def dims(p):
    """Display width/height of the first video stream (honours rotation metadata)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation:stream_tags=rotate",
                          "-of", "json", p], capture_output=True, text=True).stdout
    st = json.loads(out)["streams"][0]
    w, h = st["width"], st["height"]
    rot = abs(int(float(st.get("tags", {}).get("rotate", 0) or 0)))
    for sd in st.get("side_data_list", []):
        rot = abs(int(float(sd.get("rotation", rot) or 0)))
    return (h, w) if rot in (90, 270) else (w, h)

def frame_box(w, h, max_w=940, max_h=900, top=700):
    """Where the video goes in frame mode: scaled to fit, centred horizontally, even sizes."""
    k = min(max_w / w, max_h / h)
    vw, vh = int(w * k) // 2 * 2, int(h * k) // 2 * 2
    return vw, vh, (1080 - vw) // 2, top

def has_audio(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout.strip()
    return bool(out)

async def overlays(hook_lines, d, box=None, theme="blue"):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    hook = "<br>".join(E(x) for x in hook_lines)
    pages = {} if box else {
        "hook.png": f'<div style="position:absolute;top:300px;right:70px;left:70px;background:rgba(11,31,77,.88);border-radius:40px;padding:40px 48px;color:#fff;font-weight:700;font-size:72px;line-height:1.3;box-shadow:0 20px 50px rgba(0,0,0,.3)">{hook}</div>',
        "logo.png": '<div style="position:absolute;top:170px;right:70px;display:flex;align-items:center;gap:16px;background:rgba(255,255,255,.92);border-radius:24px;padding:12px 22px 12px 14px"><img src="mark.png" style="width:56px;height:56px"><div style="font-weight:700;font-size:28px;direction:ltr;color:#0B1F4D">Aura Clinic CRM</div></div>',
    }
    if box:  # frame mode: branded background with the hook as a title + a device bezel with a hole for the video
        vw, vh, x, y = box
        pad, ro, ri = 26, 58, 32
        ring = (f'<svg width="1080" height="1920" style="position:absolute;inset:0"><path fill="#0B0B0F" fill-rule="evenodd" d="'
                f'M{x-pad+ro},{y-pad} h{vw+2*pad-2*ro} a{ro},{ro} 0 0 1 {ro},{ro} v{vh+2*pad-2*ro} a{ro},{ro} 0 0 1 -{ro},{ro} h-{vw+2*pad-2*ro} a{ro},{ro} 0 0 1 -{ro},-{ro} v-{vh+2*pad-2*ro} a{ro},{ro} 0 0 1 {ro},-{ro} z '
                f'M{x+ri},{y} h{vw-2*ri} a{ri},{ri} 0 0 1 {ri},{ri} v{vh-2*ri} a{ri},{ri} 0 0 1 -{ri},{ri} h-{vw-2*ri} a{ri},{ri} 0 0 1 -{ri},-{ri} v-{vh-2*ri} a{ri},{ri} 0 0 1 {ri},-{ri} z"/></svg>')
        pages["bg.png"] = (f'<div style="position:absolute;inset:0;{theme_vars(theme)};background:linear-gradient(160deg,var(--g1),var(--g2) 55%,var(--g3))"></div>'
                           f'<div style="position:absolute;top:170px;right:90px;display:flex;align-items:center;gap:18px"><div style="width:80px;height:80px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center"><img src="mark.png" style="width:64px;height:64px"></div>'
                           f'<div style="font-weight:700;font-size:32px;direction:ltr;color:#fff">Aura Clinic CRM</div></div>'
                           f'<div style="position:absolute;top:330px;right:90px;left:90px;height:{y - pad - 360}px;display:flex;align-items:flex-end"><div style="font-weight:700;font-size:76px;line-height:1.28;color:#fff">{hook}</div></div>'
                           f'<div style="position:absolute;left:{x-pad}px;top:{y-pad}px;width:{vw+2*pad}px;height:{vh+2*pad}px;border-radius:{ro}px;box-shadow:0 40px 90px rgba(0,0,0,.35)"></div>')
        pages["ring.png"] = ring
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        for name, body in pages.items():
            f = os.path.join(TOOLS, f"_tmp_{name}.html")
            open(f, "w", encoding="utf-8").write(f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{CSS}html,body{{width:1080px;height:1920px;background:transparent}}</style></head><body>{body}</body></html>')
            await pg.goto("file://" + f); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(200)
            await pg.screenshot(path=os.path.join(d, name), omit_background=True); os.remove(f)
        await b.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("out"); ap.add_argument("--hook", required=True); ap.add_argument("--max", type=float, default=45)
    ap.add_argument("--fit", choices=["auto", "crop", "frame"], default="auto"); ap.add_argument("--theme", default="blue")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="real_")
    w, h = dims(a.input)
    fit = a.fit if a.fit != "auto" else ("frame" if w > h else "crop")
    box = frame_box(w, h) if fit == "frame" else None
    asyncio.run(overlays(a.hook.split("|"), tmp, box, a.theme))
    # end card via reel.py
    spec = os.path.join(tmp, "end.json")
    json.dump({"reels": [{"slug": "end", "cover_at": 1.5, "scenes": [{"type": "endcard", "dur": 2.8}]}]}, open(spec, "w"))
    subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "reel.py"), spec, tmp], check=True)
    main_v = os.path.join(tmp, "main.mp4")
    if box:   # inputs: 0 video, 1 background (looped), 2 bezel ring
        vw, vh, x, y = box
        vf = (f"[0:v]scale={vw}:{vh},fps=30,setsar=1[v0];[1:v]fps=30,format=yuva420p[bg];"
              f"[bg][v0]overlay={x}:{y}:shortest=1[v1];[v1][2:v]overlay=0:0[v]")
        imgs = ["-loop", "1", "-i", os.path.join(tmp, "bg.png"), "-i", os.path.join(tmp, "ring.png")]
    else:
        vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1[v0];"
              "[v0][2:v]overlay=0:0[v1];[v1][1:v]overlay=0:0:enable='lt(t,3.5)'[v]")
        imgs = ["-i", os.path.join(tmp, "hook.png"), "-i", os.path.join(tmp, "logo.png")]
    # no sound in the clip -> add original calm music instead of silence
    music_wav = make_track("calm_piano", a.max, os.path.join(tmp, "music.wav"), 7)
    audio = ["-map", "0:a:0"] if has_audio(a.input) else ["-i", music_wav, "-map", "3:a", "-af", "loudnorm=I=-16:TP=-1.5"]
    ff("-i", a.input, *imgs, *([] if has_audio(a.input) else audio[:2]),
       "-filter_complex", vf, "-map", "[v]", *(audio if has_audio(a.input) else audio[2:]), "-t", str(a.max),
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k", "-shortest", main_v)
    out = os.path.join(a.out, "reel.mp4")
    ff("-i", main_v, "-i", os.path.join(tmp, "end", "reel.mp4"), "-filter_complex",
       "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
       "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart", out)
    ff("-ss", "1.5", "-i", out, "-frames:v", "1", "-q:v", "2", os.path.join(a.out, "cover.jpg"))
    shutil.rmtree(tmp)
    print("ok", fit, out, os.path.getsize(out) // 1024, "KB")

if __name__ == "__main__":
    main()
