"""Edit a real (team-filmed) video into an Aura reel.

Usage: python3 edit_real.py INPUT_VIDEO OUT_DIR --hook "سطر 1|سطر 2" [--max 45]
- crops/scales to 1080x1920 (9:16), 30fps, keeps the original sound
- shows the hook text in a banner for the first 3.5 s and a small logo the whole time
- appends the 2.8 s Aura end card ("تابع @auracliniccrm") with music
- a clip without sound gets original calm music (never silent)
Outputs OUT_DIR/reel.mp4 and OUT_DIR/cover.jpg
"""
import argparse, asyncio, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import CSS, E, TOOLS  # noqa: E402
from music import make_track  # noqa: E402
from playwright.async_api import async_playwright

def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)

def has_audio(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout.strip()
    return bool(out)

async def overlays(hook_lines, d):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    hook = "<br>".join(E(x) for x in hook_lines)
    pages = {
        "hook.png": f'<div style="position:absolute;top:300px;right:70px;left:70px;background:rgba(11,31,77,.88);border-radius:40px;padding:40px 48px;color:#fff;font-weight:700;font-size:72px;line-height:1.3;box-shadow:0 20px 50px rgba(0,0,0,.3)">{hook}</div>',
        "logo.png": '<div style="position:absolute;top:170px;right:70px;display:flex;align-items:center;gap:16px;background:rgba(255,255,255,.92);border-radius:24px;padding:12px 22px 12px 14px"><img src="mark.png" style="width:56px;height:56px"><div style="font-weight:700;font-size:28px;direction:ltr;color:#0B1F4D">Aura Clinic CRM</div></div>',
    }
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
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="real_")
    asyncio.run(overlays(a.hook.split("|"), tmp))
    # end card via reel.py
    spec = os.path.join(tmp, "end.json")
    json.dump({"reels": [{"slug": "end", "cover_at": 1.5, "scenes": [{"type": "endcard", "dur": 2.8}]}]}, open(spec, "w"))
    subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "reel.py"), spec, tmp], check=True)
    main_v = os.path.join(tmp, "main.mp4")
    vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1[v0];"
          "[v0][2:v]overlay=0:0[v1];[v1][1:v]overlay=0:0:enable='lt(t,3.5)'[v]")
    # no sound in the clip -> add original calm music instead of silence
    music_wav = make_track("calm_piano", a.max, os.path.join(tmp, "music.wav"), 7)
    audio = ["-map", "0:a:0"] if has_audio(a.input) else ["-i", music_wav, "-map", "3:a", "-af", "loudnorm=I=-16:TP=-1.5"]
    ff("-i", a.input, "-i", os.path.join(tmp, "hook.png"), "-i", os.path.join(tmp, "logo.png"), *([] if has_audio(a.input) else audio[:2]),
       "-filter_complex", vf, "-map", "[v]", *(audio if has_audio(a.input) else audio[2:]), "-t", str(a.max),
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k", "-shortest", main_v)
    out = os.path.join(a.out, "reel.mp4")
    ff("-i", main_v, "-i", os.path.join(tmp, "end", "reel.mp4"), "-filter_complex",
       "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
       "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart", out)
    ff("-ss", "1.5", "-i", out, "-frames:v", "1", "-q:v", "2", os.path.join(a.out, "cover.jpg"))
    shutil.rmtree(tmp)
    print("ok", out, os.path.getsize(out) // 1024, "KB")

if __name__ == "__main__":
    main()
