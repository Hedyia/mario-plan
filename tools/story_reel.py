"""Aura Clinic CRM — animated story reel (characters + motion + burned-in Arabic subtitles + optional voice-over).

Usage: python3 story_reel.py OUT_DIR [--voice voice.mp3] [--times times.json]
  Without --voice the reel gets the brand music only (subtitles carry the story).
  With --voice the narration is mixed on top of the music (music ducked to ~18%).
  --times: JSON list of 7 scene start times + total, e.g. [0,5.5,11.5,17,23,29,36,40], to re-time scenes to a recorded voice.
Story: a patient comes on time and his booking is lost in the notebook; a second patient has the same slot; the fix.
"""
import asyncio, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import CSS, E, TOOLS, theme_vars  # noqa: E402
from music import make_track  # noqa: E402
from playwright.async_api import async_playwright

W, H, FPS = 1080, 1920, 30
RAF2 = "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"

SCRIPT = [
    "ده أستاذ محمود… حاجز كشف الساعة 6، وجه في معاده بالظبط.",
    "السكرتيرة فتحت الدفتر… قلبت صفحة، واتنين، وتلاتة… واسمه مش موجود!",
    "وفجأة دخل مريض تاني بيقول: أنا كمان حاجز الساعة 6!",
    "الصالة بتتملي، والدكتور جوه بيسأل: فين ملف المريض؟",
    "المشكلة مش في السكرتيرة… المشكلة إن الحجز متكتب في دفتر، وفي ورقة، وفي التليفون.",
    "مع Aura Clinic CRM كل الحجوزات في مكان واحد: تكتب اسم المريض… يظهرلك معاده على طول.",
    "تابعنا… كل يوم حاجة تسهّل إدارة عيادتك.",
]

ANIM = """
@keyframes sin{from{opacity:0}to{opacity:1}}
@keyframes sout{from{opacity:1}to{opacity:0}}
@keyframes rise{from{opacity:0;transform:translateY(50px)}to{opacity:1;transform:none}}
@keyframes pop{0%{opacity:0;transform:scale(.6)}70%{opacity:1;transform:scale(1.08)}100%{opacity:1;transform:none}}
@keyframes zoomin{from{transform:scale(1.18)}to{transform:scale(1)}}
@keyframes legA{0%,100%{transform:rotate(16deg)}50%{transform:rotate(-16deg)}}
@keyframes legB{0%,100%{transform:rotate(-16deg)}50%{transform:rotate(16deg)}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes breathe{0%,100%{transform:scaleY(1)}50%{transform:scaleY(1.015)}}
@keyframes flip{0%{transform:rotateY(0)}100%{transform:rotateY(-180deg)}}
@keyframes shake{0%,100%{transform:none}20%{transform:translateX(-16px) rotate(-1deg)}40%{transform:translateX(14px) rotate(1deg)}60%{transform:translateX(-9px)}80%{transform:translateX(6px)}}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
@keyframes float{0%,100%{transform:translateY(0) rotate(-4deg)}50%{transform:translateY(-22px) rotate(4deg)}}
@keyframes dash{to{stroke-dashoffset:0}}
@keyframes fall{0%{transform:none;opacity:1}100%{transform:translateY(700px) rotate(70deg);opacity:0}}
@keyframes type{from{width:0}to{width:var(--w)}}
@keyframes blink{50%{opacity:0}}
@keyframes conf{0%{opacity:0;transform:translate(0,0) scale(.4)}20%{opacity:1}100%{opacity:0;transform:translate(var(--dx),var(--dy)) rotate(260deg) scale(1)}}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
@keyframes kb{from{transform:scale(1)}to{transform:scale(1.07)}}
.scene{position:absolute;inset:0;overflow:hidden}
.emo{font-family:'Noto Color Emoji','Apple Color Emoji',sans-serif;line-height:1}
.sub{position:absolute;left:70px;right:70px;top:1235px;text-align:center}
.sub span{display:inline;background:rgba(15,10,40,.82);color:#fff;font-weight:600;font-size:50px;line-height:1.75;padding:8px 26px;border-radius:18px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.bubble{position:absolute;background:#fff;color:#1E1B4B;font-weight:700;border-radius:36px;padding:22px 34px;box-shadow:0 18px 40px rgba(30,27,75,.18);white-space:nowrap}
"""


def A(name, dur, delay, extra="both", ease="cubic-bezier(.2,.8,.2,1)"):
    return f"{name} {dur}s {ease} {delay:.2f}s {extra}"


def person(shirt, hair, skin="#F2C9A5", t_walk=None, walk_dur=0, flip=False, scale=1.0, pants="#334155"):
    """Flat character 200x420. Legs swing while walking (t_walk .. t_walk+walk_dur)."""
    steps = max(1, int(round(walk_dur / .5)))
    la = f'animation:{A("legA", .5, t_walk, f"{steps}", "linear")}' if t_walk is not None else ""
    lb = f'animation:{A("legB", .5, t_walk, f"{steps}", "linear")}' if t_walk is not None else ""
    bob = f'animation:{A("bob", .5, t_walk, f"{steps}", "ease-in-out")}' if t_walk is not None else ""
    return f"""<div style="width:{200*scale}px;height:{420*scale}px;transform:{'scaleX(-1)' if flip else 'none'}">
<div style="width:200px;height:420px;transform:scale({scale});transform-origin:0 0;{bob}">
<svg width="200" height="420" viewBox="0 0 200 420" style="overflow:visible">
  <g style="transform-origin:85px 270px;{la}"><rect x="72" y="262" width="28" height="140" rx="14" fill="{pants}"/><rect x="62" y="388" width="46" height="22" rx="11" fill="#111827"/></g>
  <g style="transform-origin:115px 270px;{lb}"><rect x="102" y="262" width="28" height="140" rx="14" fill="{pants}"/><rect x="96" y="388" width="46" height="22" rx="11" fill="#111827"/></g>
  <rect x="52" y="128" width="98" height="150" rx="44" fill="{shirt}"/>
  <rect x="36" y="140" width="26" height="110" rx="13" fill="{shirt}" opacity=".9"/>
  <rect x="140" y="140" width="26" height="110" rx="13" fill="{shirt}" opacity=".9"/>
  <circle cx="101" cy="78" r="52" fill="{skin}"/>
  <path d="M49 74 Q52 20 101 22 Q152 22 154 72 Q140 50 101 48 Q64 50 49 74Z" fill="{hair}"/>
  <circle cx="84" cy="82" r="6" fill="#1F2937"/><circle cx="120" cy="82" r="6" fill="#1F2937"/>
  <path d="M88 104 Q101 112 114 104" stroke="#1F2937" stroke-width="5" fill="none" stroke-linecap="round"/>
</svg></div></div>"""


def clock(size, t_spin=None, spin_dur=0, h=6):
    hand = f'animation:{A("spin", .6, t_spin, f"{max(1,int(spin_dur/.6))}", "linear")}' if t_spin is not None else ""
    hand2 = f'animation:{A("spin", 2.4, t_spin, f"{max(1,int(spin_dur/2.4))}", "linear")}' if t_spin is not None else ""
    return f"""<div style="width:{size}px;height:{size}px;border-radius:50%;background:#fff;border:12px solid #1E1B4B;position:relative;box-shadow:0 14px 30px rgba(0,0,0,.15)">
<div style="position:absolute;left:50%;top:50%;width:0;height:0;transform:rotate({h*30}deg)"><div style="position:absolute;left:-6px;top:{-size*.24}px;width:12px;height:{size*.24}px;border-radius:6px;background:#1E1B4B;transform-origin:6px 100%;{hand2}"></div></div>
<div style="position:absolute;left:50%;top:50%;width:0;height:0"><div style="position:absolute;left:-4px;top:{-size*.36}px;width:8px;height:{size*.36}px;border-radius:4px;background:#7C3AED;transform-origin:4px 100%;{hand}"></div></div>
<div style="position:absolute;left:50%;top:50%;width:22px;height:22px;margin:-11px;border-radius:50%;background:#1E1B4B"></div></div>"""


def room(t0, label=True):
    """Clinic reception backdrop (slow Ken Burns zoom)."""
    return f"""<div style="position:absolute;inset:0;animation:{A('kb', 6, t0, 'both', 'linear')}">
<div style="position:absolute;inset:0;background:linear-gradient(180deg,#EDE9FE 0%,#F5F3FF 62%,#DDD6FE 62%,#C4B5FD 100%)"></div>
<div style="position:absolute;top:1190px;left:0;right:0;height:14px;background:#A78BFA"></div>
<div style="position:absolute;right:90px;top:520px;background:#5B21B6;color:#fff;font-weight:700;font-size:40px;padding:14px 34px;border-radius:20px">الاستقبال</div>
<div style="position:absolute;left:120px;top:440px">{clock(170)}</div>
{'<div style="position:absolute;left:160px;top:640px;font-weight:700;font-size:44px;color:#5B21B6;direction:ltr">6:00</div>' if label else ''}
</div>"""


def desk(t0, worried_at=None):
    sweat = (f'<div class="emo" style="position:absolute;right:250px;top:640px;font-size:70px;animation:{A("pop", .5, worried_at)}">💦</div>'
             if worried_at else "")
    return f"""<div style="position:absolute;right:120px;top:700px">{person('#7C3AED', '#1F2937', scale=.95)}</div>
<div style="position:absolute;right:40px;top:960px;width:520px;height:240px;border-radius:30px 30px 0 0;background:linear-gradient(180deg,#6D28D9,#4C1D95);box-shadow:0 -6px 30px rgba(0,0,0,.12)">
<div style="position:absolute;top:24px;right:30px;left:30px;height:16px;border-radius:8px;background:rgba(255,255,255,.25)"></div></div>
<div style="position:absolute;right:300px;top:925px;width:170px;height:46px;border-radius:8px;background:#FEF3C7;border:4px solid #92400E;transform:rotate(-4deg)"></div>{sweat}"""


def subtitle(text, t0, t1):
    return (f'<div class="sub" style="animation:{A("rise", .35, t0)},{A("sout", .25, t1 - .25, "forwards", "linear")}">'
            f'<span>{E(text)}</span></div>')


def head(t0, dark=False):
    c = "#fff" if dark else "#1E1B4B"
    return (f'<div style="position:absolute;top:170px;right:90px;display:flex;align-items:center;gap:18px;animation:{A("sin", .4, t0)}">'
            f'<div style="width:80px;height:80px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(0,0,0,.18)"><img src="mark.png" style="width:64px;height:64px"></div>'
            f'<div style="font-weight:700;font-size:32px;direction:ltr;color:{c}">Aura Clinic CRM</div></div>')


def build(T):
    s = []
    def scene(i, body, dark=False):
        t0, t1 = T[i], T[i + 1]
        fade_in = A("sin", .3, t0, "both", "linear") if i else A("sin", .01, 0, "both", "linear")
        s.append(f'<div class="scene" style="animation:{fade_in},{A("sout", .3, t1 - .3, "forwards", "linear")}">{body}'
                 f'{head(t0, dark)}{subtitle(SCRIPT[i], t0 + .15, t1)}</div>')

    # 1 — patient walks in on time
    t = T[0]
    scene(0, room(t) + desk(t) +
          f'<div style="position:absolute;top:740px;left:0;animation:walkin 3.0s cubic-bezier(.3,.6,.4,1) {t+.2:.2f}s both">{person("#0EA5E9", "#3F2A1D", t_walk=t + .2, walk_dur=3.0)}</div>'
          f'<style>@keyframes walkin{{from{{transform:translateX(-260px)}}to{{transform:translateX(330px)}}}}</style>'
          f'<div class="bubble" style="left:300px;top:610px;font-size:46px;animation:{A("pop", .5, t + 3.3)}">أنا حاجز الساعة <span style="direction:ltr;display:inline-block">6:00</span> 👋</div>')

    # 2 — notebook close-up, pages flipping, name not found
    t = T[1]
    pages = "".join(
        f'<div style="position:absolute;right:0;top:0;width:360px;height:520px;transform-origin:0 50%;background:#FFFBEB;border-radius:0 24px 24px 0;'
        f'background-image:repeating-linear-gradient(0deg,transparent 0 46px,rgba(30,41,59,.12) 46px 48px);box-shadow:0 4px 10px rgba(0,0,0,.08);'
        f'animation:{A("flip", .7, t + 1.0 + k * 1.0, "both", "ease-in-out")};z-index:{5-k}"></div>' for k in range(3))
    qs = "".join(f'<div style="position:absolute;{pos};font-weight:700;font-size:{fs}px;color:#E11D48;animation:{A("pop", .45, t + d)},{A("float", 1.6, t + d + .45, "infinite", "ease-in-out")}">؟</div>'
                 for pos, fs, d in (("left:150px;top:520px", 150, 4.0), ("right:150px;top:470px", 120, 4.3), ("left:930px;top:720px", 100, 4.6)))
    scene(1, f"""<div style="position:absolute;inset:0;background:radial-gradient(circle at 50% 45%,#FEF3C7,#FDE68A 70%)"></div>
<div style="position:absolute;left:180px;top:560px;width:720px;height:520px;perspective:1800px;animation:{A('pop', .6, t + .1)}">
  <div style="position:absolute;left:0;top:0;width:360px;height:520px;background:#FFFBEB;border-radius:24px 0 0 24px;background-image:repeating-linear-gradient(0deg,transparent 0 46px,rgba(30,41,59,.12) 46px 48px);box-shadow:0 30px 60px rgba(146,64,14,.25)"></div>
  <div style="position:absolute;right:0;top:0;width:360px;height:520px;background:#FFFBEB;border-radius:0 24px 24px 0;background-image:repeating-linear-gradient(0deg,transparent 0 46px,rgba(30,41,59,.12) 46px 48px);box-shadow:0 30px 60px rgba(146,64,14,.25)"></div>
  <div style="position:absolute;left:0;top:0;width:360px;height:520px;padding:30px 34px 0 20px;font-size:34px;line-height:48px;color:#334155;font-weight:500">
    <div>أحمد <span style="direction:ltr;display:inline-block">5:00</span></div><div>سارة <span style="direction:ltr;display:inline-block">5:30</span></div>
    <div style="text-decoration:line-through;color:#94A3B8">منى <span style="direction:ltr;display:inline-block">5:30</span></div><div>كريم <span style="direction:ltr;display:inline-block">6:00</span></div>
    <div style="color:#94A3B8">؟؟ <span style="direction:ltr;display:inline-block">6:30</span></div><div>هالة <span style="direction:ltr;display:inline-block">7:00</span></div></div>
  <div style="position:absolute;left:356px;top:0;width:8px;height:520px;background:#92400E;border-radius:4px;z-index:9"></div>
  <div style="position:absolute;left:360px;top:0;width:360px;height:520px">{pages}</div>
</div>
<div style="position:absolute;left:0;right:0;top:400px;text-align:center;font-weight:700;font-size:64px;color:#92400E;animation:{A('rise', .5, t + .3)}">بندوّر على <span style="color:#E11D48">"محمود"</span>…</div>
{qs}
<div style="position:absolute;left:0;right:0;top:1090px;text-align:center;animation:{A('pop', .5, t + 4.2)}"><span style="background:#E11D48;color:#fff;font-weight:700;font-size:54px;padding:14px 40px;border-radius:24px">مش موجود ✕</span></div>""")

    # 3 — a second patient with the same slot
    t = T[2]
    scene(2, room(t, label=False) + desk(t, worried_at=t + 2.4) +
          f'<div style="position:absolute;top:740px;left:330px;animation:{A("shake", .6, t + 2.2, "2")}">{person("#0EA5E9", "#3F2A1D")}</div>'
          f'<div style="position:absolute;top:760px;left:0;animation:walkin2 1.6s cubic-bezier(.3,.6,.4,1) {t+.2:.2f}s both">{person("#F97316", "#111827", t_walk=t + .2, walk_dur=1.6, scale=.94)}</div>'
          f'<style>@keyframes walkin2{{from{{transform:translateX(-300px)}}to{{transform:translateX(90px)}}}}</style>'
          f'<div class="bubble" style="left:40px;top:560px;font-size:44px;animation:{A("pop", .45, t + 1.9)}">وأنا كمان <span style="direction:ltr;display:inline-block">6:00</span>!</div>'
          f'<div class="bubble" style="left:390px;top:640px;font-size:44px;animation:{A("pop", .45, t + 2.4)}">إزاي يعني؟! 😳</div>'
          f'<div class="emo" style="position:absolute;left:300px;top:840px;font-size:110px;animation:{A("pop", .4, t + 2.6)},{A("pulse", .5, t + 3.0, "6", "ease-in-out")}">⚡</div>')

    # 4 — waiting room fills, clock spins, doctor asks for the file
    t = T[3]
    shirts = ["#22C55E", "#EAB308", "#EC4899", "#0EA5E9", "#F97316"]
    chairs = "".join(
        f'<div style="position:absolute;left:{70 + k*190}px;top:980px;width:170px;height:150px;border-radius:26px 26px 10px 10px;background:#7C3AED"></div>'
        f'<div style="position:absolute;left:{78 + k*190}px;top:{760}px;animation:{A("pop", .45, t + .5 + k*.7)}">{person(shirts[k], "#1F2937", scale=.75)}</div>'
        for k in range(5))
    scene(3, f"""<div style="position:absolute;inset:0;background:linear-gradient(180deg,#EDE9FE 0%,#F5F3FF 64%,#C4B5FD 64%)"></div>
<div style="position:absolute;left:0;right:0;top:330px;text-align:center;font-weight:700;font-size:62px;color:#1E1B4B;animation:{A('rise', .5, t + .2)}">صالة الانتظار…</div>
<div style="position:absolute;left:440px;top:440px;animation:{A('pop', .5, t + .3)}">{clock(200, t_spin=t + .8, spin_dur=5)}</div>
<div style="position:absolute;right:60px;top:430px;width:150px;height:260px;border-radius:16px 16px 0 0;background:#5B21B6"><div style="position:absolute;left:24px;top:120px;width:16px;height:16px;border-radius:50%;background:#FDE68A"></div></div>
<div class="bubble" style="right:50px;top:650px;font-size:40px;animation:{A('pop', .45, t + 3.4)},{A('shake', .5, t + 4.0)}">🩺 فين ملف المريض؟</div>
{chairs}""")

    # 5 — the booking lives in 3 places; they fall apart
    t = T[4]
    items = [("📒", "دفتر", 140, 470), ("📝", "ورقة", 650, 520), ("📞", "تليفون", 390, 830)]
    nodes = "".join(
        f'<div style="position:absolute;left:{x}px;top:{y}px;width:290px;text-align:center;animation:{A("pop", .5, t + .4 + k*.6)},{A("float", 1.8, t + 1 + k*.6, "2", "ease-in-out")},{A("fall", 1.0, t + 4.6 + k*.12, "forwards", "ease-in")}">'
        f'<div style="width:220px;height:220px;margin:0 auto;border-radius:60px;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 24px 50px rgba(0,0,0,.25)"><span class="emo" style="font-size:130px">{e}</span></div>'
        f'<div style="margin-top:20px;font-weight:700;font-size:50px;color:#fff">{E(lbl)}</div></div>'
        for k, (e, lbl, x, y) in enumerate(items))
    scene(4, f"""<div style="position:absolute;inset:0;background:linear-gradient(160deg,#1E1B4B,#5B21B6 60%,#7C3AED)"></div>
<svg style="position:absolute;inset:0" width="1080" height="1920"><g fill="none" stroke="#F5D0FE" stroke-width="8" stroke-dasharray="26 18" style="animation:{A('fall', 1.0, t + 4.6, 'forwards', 'ease-in')}">
<path d="M285 600 C 500 420, 640 760, 795 650" pathLength="1" style="stroke-dasharray:1;stroke-dashoffset:1;animation:{A('dash', 1.0, t + 2.0)}"/>
<path d="M795 700 C 760 900, 620 860, 535 960" pathLength="1" style="stroke-dasharray:1;stroke-dashoffset:1;animation:{A('dash', 1.0, t + 2.5)}"/>
<path d="M285 650 C 200 860, 380 900, 535 960" pathLength="1" style="stroke-dasharray:1;stroke-dashoffset:1;animation:{A('dash', 1.0, t + 3.0)}"/></g></svg>
{nodes}
<div style="position:absolute;left:0;right:0;top:340px;text-align:center;font-weight:700;font-size:62px;color:#fff;animation:{A('rise', .5, t + .2)}">الحجز في <span style="color:#F5D0FE">3 أماكن</span></div>""", dark=True)

    # 6 — the fix: search the name, the appointment pops up
    t = T[5]
    conf = "".join(
        f'<div style="position:absolute;left:540px;top:900px;width:22px;height:22px;border-radius:{"50%" if k % 2 else "4px"};background:{c};--dx:{dx}px;--dy:{dy}px;animation:{A("conf", 1.3, t + 4.0, "both", "ease-out")}"></div>'
        for k, (c, dx, dy) in enumerate([("#F5D0FE", -380, -420), ("#FDE68A", 360, -380), ("#86EFAC", -300, 200), ("#FDA4AF", 330, 240), ("#fff", -120, -520), ("#C4B5FD", 160, -500), ("#FDE68A", -420, -60), ("#86EFAC", 420, -40)]))
    scene(5, f"""<div style="position:absolute;inset:0;background:linear-gradient(160deg,#4C1D95,#6D28D9 55%,#A78BFA)"></div>
<div style="position:absolute;left:0;right:0;top:330px;text-align:center;font-weight:700;font-size:60px;color:#fff;animation:{A('rise', .5, t + .1)}">كل الحجوزات في <span style="color:#F5D0FE">مكان واحد</span></div>
<div style="position:absolute;left:190px;top:470px;width:700px;height:740px;border-radius:70px;background:#0B0B0F;box-shadow:0 40px 90px rgba(0,0,0,.4);animation:up .8s cubic-bezier(.2,.8,.2,1) {t+.3:.2f}s both">
 <div style="position:absolute;inset:18px;border-radius:54px;background:#F5F3FF;overflow:hidden">
  <div style="position:absolute;top:60px;right:40px;left:40px;height:100px;border-radius:30px;background:#fff;box-shadow:0 8px 20px rgba(0,0,0,.06);display:flex;align-items:center;gap:20px;padding:0 30px">
   <span class="emo" style="font-size:44px">🔍</span>
   <span style="display:inline-block;overflow:hidden;white-space:nowrap;--w:190px;font-weight:600;font-size:48px;color:#1E1B4B;animation:type 1.0s steps(5,end) {t+1.3:.2f}s both">محمود</span>
   <span style="width:4px;height:52px;background:#7C3AED;animation:blink .8s steps(1) {t+.8:.2f}s 5"></span>
  </div>
  <div style="position:absolute;top:210px;right:40px;left:40px;border-radius:36px;background:#fff;padding:36px;box-shadow:0 18px 40px rgba(76,29,149,.18);animation:{A('pop', .55, t + 2.6)}">
   <div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:700;font-size:50px;color:#1E1B4B">أستاذ محمود</div>
     <div style="width:76px;height:76px;border-radius:50%;background:#22C55E;color:#fff;font-size:50px;font-weight:700;display:flex;align-items:center;justify-content:center;animation:{A('pop', .5, t + 3.4)}">✓</div></div>
   <div style="margin-top:24px;display:flex;gap:18px;flex-wrap:wrap">
     <span style="background:#EDE9FE;color:#5B21B6;font-weight:700;font-size:40px;padding:10px 26px;border-radius:18px">النهارده · <span style="direction:ltr;display:inline-block">6:00</span></span>
     <span style="background:#DCFCE7;color:#166534;font-weight:700;font-size:40px;padding:10px 26px;border-radius:18px">متسجل</span></div>
  </div>
  <div style="position:absolute;top:500px;right:40px;left:40px;display:flex;gap:16px;animation:{A('rise', .5, t + 3.8)}">
   <div style="flex:1;height:90px;border-radius:26px;background:#fff;display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:600;color:#5B21B6">📁 الملف</div>
   <div style="flex:1;height:90px;border-radius:26px;background:#fff;display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:600;color:#5B21B6">🧾 الفاتورة</div></div>
 </div></div>
<style>@keyframes up{{from{{opacity:0;transform:translateY(500px)}}to{{opacity:1;transform:none}}}}</style>
{conf}""", dark=True)

    # 7 — end card
    t = T[6]
    scene(6, f"""<div style="position:absolute;inset:0;background:linear-gradient(160deg,#1E1B4B,#5B21B6 55%,#A78BFA)"></div>
<div style="position:absolute;top:400px;right:90px;left:90px;text-align:center">
 <div style="animation:{A('pop', .6, t + .1)}"><div style="display:inline-flex;width:230px;height:230px;border-radius:60px;background:#fff;align-items:center;justify-content:center;box-shadow:0 30px 70px rgba(0,0,0,.25)"><img src="mark.png" style="width:190px;height:190px"></div></div>
 <div style="animation:{A('rise', .5, t + .4)}"><div style="margin-top:44px;font-weight:700;font-size:48px;direction:ltr;color:#fff">Aura Clinic CRM</div></div>
 <div style="animation:{A('rise', .5, t + .7)}"><div style="margin-top:60px;font-weight:700;font-size:90px;line-height:1.3;color:#fff">تابع <span class="ltr" style="color:#F5D0FE">@auracliniccrm</span></div></div>
 <div style="animation:{A('rise', .5, t + 1.1)}"><div style="margin-top:50px;display:inline-block;background:#fff;color:#1E1B4B;font-weight:700;font-size:42px;padding:28px 48px;border-radius:26px">ابعتلنا وهنرد على كل استفساراتك</div></div>
</div>""", dark=True)

    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{ANIM}:root{{{theme_vars("violet")}}}'
            f'body{{width:{W}px;height:{H}px;overflow:hidden;background:#1E1B4B}}</style></head><body>{"".join(s)}</body></html>')


async def main(out_dir, voice=None, times=None):
    T = times or [0, 5.5, 11.5, 17, 23, 29, 36, 40]
    total = T[-1]
    os.makedirs(out_dir, exist_ok=True)
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else await p.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        f = os.path.join(TOOLS, "_tmp_story_reel.html")
        open(f, "w", encoding="utf-8").write(build(T))
        await pg.goto("file://" + f); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getAnimations().forEach(a=>a.pause())")
        frames = tempfile.mkdtemp(prefix="sframes_")
        n = int(round(total * FPS))
        for i in range(n):
            await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={i * 1000 / FPS})"); await pg.evaluate(RAF2)
            await pg.screenshot(path=os.path.join(frames, f"f{i:05d}.jpg"), type="jpeg", quality=92)
        await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={(T[2] + 3.2) * 1000})"); await pg.evaluate(RAF2)
        await pg.screenshot(path=os.path.join(out_dir, "cover.jpg"), type="jpeg", quality=92)
        await b.close(); os.remove(f)
    wav = make_track("soft_lofi", total, os.path.join(frames, "music.wav"), 313)
    out = os.path.join(out_dir, "reel.mp4")
    if voice:
        af = ["-filter_complex", "[1:a]volume=0.18[m];[2:a]adelay=200|200,volume=1.0[v];[m][v]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000[a]",
              "-map", "0:v", "-map", "[a]"]
        ins = ["-i", wav, "-i", voice]
    else:
        af = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"]
        ins = ["-i", wav]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.jpg"), *ins, *af,
                    "-t", f"{total}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                    "-r", str(FPS), "-g", "60", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(frames)
    print(out, f"{total:.1f}s", n, "frames", os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    a = sys.argv[1:]
    v = a[a.index("--voice") + 1] if "--voice" in a else None
    tm = json.load(open(a[a.index("--times") + 1])) if "--times" in a else None
    asyncio.run(main(a[0], v, tm))
