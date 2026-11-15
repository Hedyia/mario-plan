"""Narrated motion-graphic story with animated characters (1080x1920, 30fps).

Usage: python3 story_anim.py spec.json OUT_DIR
spec = {"slug": "...", "music": "soft_lofi", "scenes": [{"id": "s1", "dur": 4.2, "sub": "subtitle text", "audio": "path.wav"?}, ...]}
Each scene id maps to a visual builder below (SCENES). If a scene has "audio", the narration clip starts 0.25 s into the scene.
Output: OUT_DIR/<slug>/reel.mp4 (narration + quiet music bed, loudness -16 LUFS) and cover.jpg.
"""
import asyncio, json, os, shutil, subprocess, sys, tempfile, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from music import make_track
from playwright.async_api import async_playwright

TOOLS = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
E = html.escape
FONT = "".join(
    f"@font-face{{font-family:'Plex';src:url('fonts/ibm-plex-sans-arabic-{sub}-{w}-normal.woff2') format('woff2');font-weight:{w}}}"
    for sub in ("arabic", "latin") for w in (400, 500, 600, 700))

CSS = FONT + """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:#FFF7ED;font-family:'Plex',sans-serif}
.ltr{direction:ltr;unicode-bidi:isolate;display:inline-block}
.emo{font-family:'Noto Color Emoji',sans-serif}
.scene{position:absolute;inset:0;opacity:0;overflow:hidden;direction:rtl}
.abs{position:absolute}
@keyframes show{0%{opacity:0}4%{opacity:1}96%{opacity:1}100%{opacity:0}}
@keyframes pop{0%{transform:scale(.3);opacity:0}70%{transform:scale(1.08);opacity:1}100%{transform:scale(1);opacity:1}}
@keyframes rise{from{transform:translateY(60px);opacity:0}to{transform:none;opacity:1}}
@keyframes fadein{from{opacity:0}to{opacity:1}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes legA{0%,100%{transform:rotate(18deg)}50%{transform:rotate(-18deg)}}
@keyframes legB{0%,100%{transform:rotate(-18deg)}50%{transform:rotate(18deg)}}
@keyframes armA{0%,100%{transform:rotate(-14deg)}50%{transform:rotate(14deg)}}
@keyframes wave{0%,100%{transform:rotate(-150deg)}50%{transform:rotate(-115deg)}}
@keyframes look{0%,100%{transform:scaleX(1)}50%{transform:scaleX(-1)}}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-12px)}75%{transform:translateX(12px)}}
@keyframes wobble{0%,100%{transform:rotate(-6deg)}50%{transform:rotate(6deg)}}
@keyframes fall{from{transform:translateY(-900px) rotate(var(--r0))}to{transform:translateY(0) rotate(var(--r1))}}
@keyframes stamp{0%{transform:scale(3) rotate(-12deg);opacity:0}60%{transform:scale(.92) rotate(-12deg);opacity:1}100%{transform:scale(1) rotate(-12deg);opacity:1}}
@keyframes sweat{0%{transform:translateY(0);opacity:0}20%{opacity:1}100%{transform:translateY(40px);opacity:0}}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
@keyframes sigh{0%,100%{transform:translateY(0) scaleY(1)}50%{transform:translateY(8px) scaleY(.97)}}
.sub{position:absolute;left:70px;right:70px;top:1330px;text-align:center}
.sub span{display:inline;background:#111827;color:#fff;font-weight:700;font-size:54px;line-height:1.75;padding:8px 22px;border-radius:18px;
  -webkit-box-decoration-break:clone;box-decoration-break:clone}
.bubble{position:absolute;background:#fff;border:5px solid #111827;border-radius:40px;padding:22px 34px;font-weight:700;font-size:46px;color:#111827;line-height:1.4;box-shadow:0 10px 0 #111827}
.tag{position:absolute;background:#1D4ED8;color:#fff;font-weight:700;font-size:34px;padding:12px 26px;border-radius:999px}
"""


def anim(name, dur, delay, extra="both", ease="cubic-bezier(.2,.8,.2,1)", it="1"):
    return f"animation:{name} {dur}s {ease} {delay:.2f}s {it} {extra};"


def person(kind, walk=False, wave=False, t=0.0, scale=1.0, flip=False, extra=""):
    """Flat SVG character. kind: doctor | secretary | patient | patient2."""
    P = {
        "doctor": dict(skin="#E0A979", hair="#2B1B12", shirt="#FFFFFF", pants="#334155", acc="coat"),
        "secretary": dict(skin="#D9A066", hair="#BE185D", shirt="#F472B6", pants="#1E3A8A", acc="hijab"),
        "patient": dict(skin="#C68642", hair="#1F2937", shirt="#2563EB", pants="#374151", acc="cap"),
        "patient2": dict(skin="#E8B48A", hair="#7C2D12", shirt="#16A34A", pants="#78350F", acc="bun"),
    }[kind]
    leg_anim_a = f"animation:legA .55s ease-in-out {t:.2f}s infinite;" if walk else ""
    leg_anim_b = f"animation:legB .55s ease-in-out {t:.2f}s infinite;" if walk else ""
    arm_anim = f"animation:armA .55s ease-in-out {t:.2f}s infinite;" if walk else ""
    wave_anim = f"animation:wave .7s ease-in-out {t:.2f}s infinite;" if wave else arm_anim
    bob = f"animation:bob .55s ease-in-out {t:.2f}s infinite;" if walk else f"animation:sigh 2.4s ease-in-out {t:.2f}s infinite;"
    head_extra = ""
    if P["acc"] == "hijab":
        head_extra = f'<path d="M58 70 Q100 0 142 70 L150 135 Q100 160 50 135 Z" fill="{P["hair"]}"/>'
        hair = ""
    elif P["acc"] == "cap":
        hair = f'<path d="M62 62 Q100 22 138 62 L138 70 L62 70 Z" fill="#DC2626"/><rect x="120" y="62" width="40" height="10" rx="5" fill="#DC2626"/>'
    elif P["acc"] == "bun":
        hair = f'<circle cx="100" cy="36" r="18" fill="{P["hair"]}"/><path d="M60 78 Q100 30 140 78 Q132 56 100 52 Q68 56 60 78Z" fill="{P["hair"]}"/>'
    else:
        hair = f'<path d="M60 78 Q100 34 140 78 Q136 52 100 50 Q64 52 60 78Z" fill="{P["hair"]}"/>'
    face = (f'<circle cx="100" cy="90" r="42" fill="{P["skin"]}"/>{hair}'
            f'<circle cx="86" cy="90" r="5" fill="#111"/><circle cx="114" cy="90" r="5" fill="#111"/>'
            f'<path d="M88 108 Q100 116 112 108" stroke="#111" stroke-width="4" fill="none" stroke-linecap="round"/>')
    if kind == "doctor":
        face += '<circle cx="86" cy="90" r="11" fill="none" stroke="#111" stroke-width="3"/><circle cx="114" cy="90" r="11" fill="none" stroke="#111" stroke-width="3"/><line x1="97" y1="90" x2="103" y2="90" stroke="#111" stroke-width="3"/>'
    if P["acc"] == "hijab":
        face = (f'<path d="M50 80 Q100 -10 150 80 L156 150 Q100 175 44 150 Z" fill="{P["hair"]}"/>'
                f'<circle cx="100" cy="92" r="38" fill="{P["skin"]}"/>'
                f'<circle cx="87" cy="92" r="5" fill="#111"/><circle cx="113" cy="92" r="5" fill="#111"/>'
                f'<path d="M89 108 Q100 115 111 108" stroke="#111" stroke-width="4" fill="none" stroke-linecap="round"/>')
    coat = ""
    if P["acc"] == "coat":
        coat = ('<path d="M100 140 L100 300" stroke="#CBD5E1" stroke-width="4"/>'
                '<path d="M78 150 Q70 210 96 230" stroke="#0F766E" stroke-width="6" fill="none"/><circle cx="96" cy="234" r="9" fill="#0F766E"/>')
    body = (f'<rect x="58" y="134" width="84" height="170" rx="34" fill="{P["shirt"]}" stroke="{"#CBD5E1" if kind=="doctor" else "none"}" stroke-width="4"/>{coat}')
    legs = (f'<g style="transform-origin:86px 290px;{leg_anim_a}"><rect x="72" y="284" width="26" height="120" rx="13" fill="{P["pants"]}"/><rect x="66" y="392" width="40" height="18" rx="9" fill="#111827"/></g>'
            f'<g style="transform-origin:114px 290px;{leg_anim_b}"><rect x="102" y="284" width="26" height="120" rx="13" fill="{P["pants"]}"/><rect x="96" y="392" width="40" height="18" rx="9" fill="#111827"/></g>')
    arms = (f'<g style="transform-origin:66px 150px;{arm_anim}"><rect x="46" y="146" width="24" height="120" rx="12" fill="{P["shirt"]}" stroke="{"#CBD5E1" if kind=="doctor" else "none"}" stroke-width="3"/><circle cx="58" cy="270" r="13" fill="{P["skin"]}"/></g>'
            f'<g style="transform-origin:134px 150px;{wave_anim}"><rect x="130" y="146" width="24" height="120" rx="12" fill="{P["shirt"]}" stroke="{"#CBD5E1" if kind=="doctor" else "none"}" stroke-width="3"/><circle cx="142" cy="270" r="13" fill="{P["skin"]}"/></g>')
    fl = "scaleX(-1)" if flip else ""
    base = scale; scale = scale * 1.25
    off = f"margin-top:{-420*(scale-base):.0f}px;margin-left:{-100*(scale-base):.0f}px;"
    return (f'<div style="width:{200*scale}px;height:{420*scale}px;{off}{extra}"><div style="width:200px;height:420px;transform-origin:0 0;transform:scale({scale}) {fl};{"transform-origin:100px 0;" if flip else ""}">'
            f'<div style="width:200px;height:420px;{bob}"><svg viewBox="0 0 200 420" width="200" height="420">{legs}{arms}{body}{face}</svg></div></div></div>')


def room(wall="#FDE68A", floor="#F59E0B", door=True, sign=None):
    d = ('<div class="abs" style="left:760px;top:520px;width:220px;height:520px;background:#92400E;border-radius:16px 16px 0 0;border:8px solid #78350F">'
         '<div class="abs" style="left:24px;top:250px;width:22px;height:22px;border-radius:50%;background:#FCD34D"></div></div>') if door else ""
    s = (f'<div class="abs" style="left:110px;top:330px;background:#fff;border:6px solid #111827;border-radius:22px;padding:14px 34px;font-weight:700;font-size:52px;color:#111827;box-shadow:0 8px 0 #111827">{E(sign)}</div>') if sign else ""
    return (f'<div class="abs" style="inset:0;background:{wall}"></div>'
            f'<div class="abs" style="left:0;right:0;top:1040px;bottom:0;background:{floor}"></div>'
            f'<div class="abs" style="left:0;right:0;top:1032px;height:16px;background:rgba(0,0,0,.12)"></div>{d}{s}')


def desk(x=120, y=840, w=520):
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;height:40px;background:#7C3AED;border-radius:12px"></div>'
            f'<div class="abs" style="left:{x+30}px;top:{y+40}px;width:{w-60}px;height:170px;background:#6D28D9;border-radius:0 0 16px 16px"></div>')


def notebook(x, y, t, rot=-8, q=False):
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:150px;height:110px;background:#1E3A8A;border-radius:10px;transform:rotate({rot}deg);box-shadow:0 8px 0 rgba(0,0,0,.2)">'
            f'<div class="abs" style="left:14px;top:12px;right:14px;bottom:12px;background:#FEF3C7;border-radius:6px;font-size:22px;font-weight:700;color:#1E3A8A;text-align:center;padding-top:22px">دفتر المواعيد</div></div>'
            + (f'<div class="abs" style="left:{x+120}px;top:{y-90}px;{anim("pop", .5, t)}"><span style="font-size:110px;font-weight:700;color:#DC2626">؟</span></div>' if q else ""))


def sub(text, t0):
    return f'<div class="sub" style="{anim("rise", .45, t0 + .1)}"><span>{E(text)}</span></div>'


# ---------- scenes: each returns inner html, times relative to scene start t ----------
def s1(t, d):
    return (room(sign="عيادة د. أحمد")
            + f'<div class="abs" style="left:330px;top:640px;{anim("pop", .6, t + .3)}">{person("doctor", wave=True, t=t)}</div>'
            + f'<div class="abs" style="left:150px;top:470px;{anim("stamp", .5, t + d * .64)}"><div style="border:10px solid #DC2626;color:#DC2626;font-weight:700;font-size:92px;padding:6px 40px;border-radius:24px;background:rgba(255,255,255,.85)">من غير سيستم</div></div>')


def s2(t, d):
    return (room(wall="#DBEAFE", floor="#93C5FD")
            + desk()
            + f'<div class="abs" style="left:420px;top:770px;width:70px;height:70px;background:#fff;border:6px solid #111827;border-radius:0 0 18px 18px"></div>'
            + f'<div class="abs" style="left:432px;top:705px;font-size:56px;{anim("fadein", .4, t)}"><span class="emo">☕</span></div>'
            + notebook(380, 790, t, rot=4)
            + f'<div class="abs" style="top:560px;left:0;{anim("walk1", d * .9, t + .2, ease="linear")}">{person("secretary", walk=True, t=t, scale=1.05)}</div>'
            + f'<div class="abs" style="left:640px;top:520px;font-size:120px;{anim("pop", .5, t + 1.2)}"><span class="emo" style="display:inline-block;animation:wobble 1s ease-in-out {t+1.2:.2f}s infinite">🔍</span></div>'
            + f'<style>@keyframes walk1{{0%{{transform:translateX(780px) scaleX(1)}}45%{{transform:translateX(620px)}}55%{{transform:translateX(620px) scaleX(-1)}}100%{{transform:translateX(760px) scaleX(-1)}}}}</style>')


def s3(t, d):
    return (room(wall="#FCE7F3", floor="#F9A8D4")
            + desk(x=80, y=860, w=460)
            + notebook(370, 790, t + d * .7, rot=-6, q=True)
            + f'<div class="abs" style="left:120px;top:640px">{person("secretary", t=t)}</div>'
            + f'<div class="abs" style="top:600px;left:0;{anim("enter", 1.6, t + .1)}">{person("patient", walk=True, t=t, flip=True)}</div>'
            + f'<div class="bubble" style="left:470px;top:330px;{anim("pop", .5, t + 1.6)}">أنا حاجز من أسبوع!</div>'
            + f'<style>@keyframes enter{{from{{transform:translateX(1100px)}}to{{transform:translateX(640px)}}}}</style>')


def s4(t, d):
    paper = '<div style="width:90px;height:110px;background:#fff;border:5px solid #111827;border-radius:8px;transform:rotate(-8deg)"><div style="margin:18px 12px;height:6px;background:#94A3B8;border-radius:3px;box-shadow:0 18px 0 #94A3B8,0 36px 0 #94A3B8"></div></div>'
    return (room(wall="#DCFCE7", floor="#86EFAC", door=False)
            + f'<div class="abs" style="left:420px;top:180px;width:220px;height:220px;border-radius:50%;background:#fff;border:12px solid #111827;{anim("pop", .5, t + .2)}">'
              f'<div class="abs" style="left:108px;top:40px;width:12px;height:84px;background:#111827;border-radius:6px;transform-origin:6px 84px;animation:spin 1.2s linear {t:.2f}s infinite"></div>'
              f'<div class="abs" style="left:58px;top:118px;font-weight:700;font-size:34px;direction:ltr">10:00</div></div>'
            + f'<div class="abs" style="left:150px;top:600px;animation:shake .5s ease-in-out {t + 1.4:.2f}s infinite">{person("patient", t=t)}</div>'
            + f'<div class="abs" style="left:610px;top:600px;animation:shake .5s ease-in-out {t + 1.6:.2f}s infinite">{person("patient2", t=t)}</div>'
            + f'<div class="abs" style="left:250px;top:700px;{anim("pop", .5, t + 2.4)}">{paper}</div>'
            + f'<div class="abs" style="left:560px;top:700px;{anim("pop", .5, t + 2.6)}">{paper}</div>'
            + f'<div class="bubble" style="left:60px;top:430px;font-size:40px;{anim("pop", .45, t + 2.9)}">أنا الأول!</div>'
            + f'<div class="bubble" style="left:680px;top:430px;font-size:40px;{anim("pop", .45, t + 3.3)}">لا أنا!</div>')


def s5(t, d):
    box = lambda x, y, dl, lab="": (f'<div class="abs" style="left:{x}px;top:{y}px;width:170px;height:130px;background:#D97706;border:6px solid #78350F;border-radius:10px;{anim("rise", .45, t + dl)}">'
                                    f'<div style="text-align:center;font-weight:700;font-size:28px;color:#fff;padding-top:40px">{E(lab)}</div></div>')
    return (room(wall="#EDE9FE", floor="#C4B5FD", door=False)
            + f'<div class="abs" style="left:110px;top:620px">{person("doctor", wave=True, t=t)}</div>'
            + f'<div class="bubble" style="left:110px;top:400px;{anim("pop", .45, t + 1.0)}">هاتوا ملف المريض!</div>'
            + box(560, 900, 3.2, "ملفات 2019") + box(740, 900, 3.6, "ملفات 2021") + box(650, 770, 4.0, "متنوع")
            + f'<div class="abs" style="left:560px;top:600px;width:380px;height:150px;border:10px solid #475569;border-radius:20px;{anim("pop", .5, t + d * .84)}"></div>'
            + f'<div class="abs" style="left:690px;top:560px;font-size:130px;{anim("pop", .5, t + d * .86)}"><span class="emo">🔒</span></div>')


def s6(t, d):
    rec = "".join(
        f'<div class="abs" style="left:{x}px;top:{y}px;--r0:{r0}deg;--r1:{r1}deg;{anim("fall", .9, t + 2.8 + dl, ease="cubic-bezier(.3,.9,.4,1.1)")}">'
        f'<div style="width:120px;height:150px;background:#fff;border:4px solid #CBD5E1;border-radius:6px;box-shadow:0 6px 12px rgba(0,0,0,.15)"><div style="margin:20px 14px;height:6px;background:#CBD5E1;border-radius:3px;box-shadow:0 20px 0 #CBD5E1,0 40px 0 #CBD5E1,0 60px 0 #CBD5E1"></div></div></div>'
        for x, y, r0, r1, dl in [(120, 900, -40, -12, .2), (230, 880, 30, 9, .35), (330, 910, -20, -4, .5), (180, 830, 50, 18, .65), (280, 820, -30, -15, .8), (420, 900, 20, 6, .95)])
    nums = "".join(
        f'<div class="abs" style="left:{x}px;top:{y}px;{anim("pop", .45, t + d * dl)}"><div class="ltr" style="background:{c};color:#fff;font-weight:700;font-size:64px;padding:10px 30px;border-radius:22px;box-shadow:0 8px 0 rgba(0,0,0,.2)">{n}</div></div>'
        for x, y, n, c, dl in [(560, 380, "48,200", "#DC2626", .69), (650, 510, "51,750", "#2563EB", .75), (580, 640, "39,900", "#16A34A", .81)])
    calc = ('<div class="abs" style="left:640px;top:820px;width:230px;height:300px;background:#1F2937;border-radius:28px;padding:22px;' + anim("pop", .5, t + 2.4) + '">'
            '<div style="height:70px;background:#A7F3D0;border-radius:12px;text-align:left;font-weight:700;font-size:44px;padding:8px 14px" class="ltr">???</div>'
            '<div style="margin-top:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px">' + '<div style="height:44px;background:#4B5563;border-radius:10px"></div>' * 9 + '</div></div>')
    return (room(wall="#FEF3C7", floor="#FCD34D", door=False)
            + f'<div class="tag" style="left:110px;top:300px;background:#111827;{anim("pop", .45, t + 1.2)}">آخر الشهر</div>'
            + calc + rec + nums
            + f'<div class="abs" style="left:430px;top:820px;font-size:100px;{anim("pop", .5, t + d * .9)}"><span class="emo">🤯</span></div>')


def s7(t, d):
    return (room(wall="#E0F2FE", floor="#7DD3FC", door=False)
            + f'<div class="abs" style="left:60px;top:640px">{person("secretary", t=t, scale=.85)}</div>'
            + f'<div class="abs" style="left:260px;top:610px">{person("doctor", t=t, scale=.92)}</div>'
            + f'<div class="abs" style="left:480px;top:640px">{person("patient", t=t, scale=.85)}</div>'
            + f'<div class="abs" style="left:680px;top:650px">{person("patient2", t=t, scale=.85)}</div>'
            + f'<div class="abs" style="left:390px;top:560px;font-size:60px;{anim("sweat", 1.2, t + .3, it="infinite")}"><span class="emo">💧</span></div>'
            + f'<div class="abs" style="left:90px;right:90px;top:150px;text-align:center;{anim("rise", .5, t + .2)}"><div style="font-weight:700;font-size:70px;color:#111827;line-height:1.3">مش محتاجين سكرتيرة زيادة…</div></div>'
            + f'<div class="abs" style="left:90px;right:90px;top:370px;text-align:center;{anim("stamp", .5, t + d * .68)}"><div style="display:inline-block;background:#1D4ED8;color:#fff;font-weight:700;font-size:96px;padding:6px 44px;border-radius:26px">محتاجين سيستم</div></div>')


def s8(t, d):
    rows = "".join(
        f'<div style="{anim("rise", .45, t + .9 + .35 * k)};display:flex;align-items:center;gap:22px;justify-content:flex-start;margin-top:22px;font-size:50px;font-weight:600;color:#fff">'
        f'<span class="emo" style="font-size:52px">{e}</span>{E(x)}</div>'
        for k, (e, x) in enumerate([("📅", "المواعيد"), ("🗂️", "ملفات المرضى"), ("🧾", "الفواتير")]))
    return (f'<div class="abs" style="inset:0;background:linear-gradient(160deg,#1E3A8A,#2563EB 55%,#38BDF8)"></div>'
            f'<div class="abs" style="left:0;right:0;top:300px;text-align:center;{anim("pop", .6, t + .1)}"><div style="display:inline-flex;width:200px;height:200px;border-radius:52px;background:#fff;align-items:center;justify-content:center"><img src="mark.png" style="width:160px;height:160px"></div>'
            f'<div style="margin-top:26px;font-weight:700;font-size:56px;color:#fff;direction:ltr">Aura Clinic CRM</div></div>'
            f'<div class="abs" style="left:150px;right:150px;top:680px">{rows}'
            f'<div style="{anim("rise", .45, t + 2.1)};margin-top:40px;font-size:44px;font-weight:700;color:#FDE68A">كله في مكان واحد</div>'
            f'<div style="{anim("fadein", .45, t + 2.4)};margin-top:16px;font-size:34px;line-height:1.5;color:rgba(255,255,255,.88)">ملفات المرضى في كل الباقات، والمواعيد والفواتير من باقة <span class="ltr">Starter</span> وأعلى</div></div>'
            f'<div class="abs" style="left:0;right:0;top:1260px;text-align:center;{anim("pop", .5, t + 5.2)}"><div style="display:inline-block;background:#fff;color:#1E3A8A;font-weight:700;font-size:52px;padding:22px 46px;border-radius:26px">تابع <span class="ltr">@auracliniccrm</span></div></div>')


SCENES = {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5, "s6": s6, "s7": s7, "s8": s8}


def build(spec):
    t, parts = 0.0, []
    for sc in spec["scenes"]:
        d = sc["dur"]
        inner = SCENES[sc["id"]](t, d) + (sub(sc["sub"], t) if sc.get("sub") and sc["id"] != "s8" else "")
        parts.append(f'<div class="scene" style="{anim("show", d, t, extra="both", ease="linear")}">{inner}</div>')
        t += d
    return (f'<!doctype html><html lang="ar" dir="ltr"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'), t


RAF2 = "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"


async def main(spec_path, out_dir):
    spec = json.load(open(spec_path, encoding="utf-8"))
    page_html, total = build(spec)
    d = os.path.join(out_dir, spec["slug"]); os.makedirs(d, exist_ok=True)
    f = os.path.join(TOOLS, f"_tmp_anim_{spec['slug']}.html"); open(f, "w", encoding="utf-8").write(page_html)
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    frames = tempfile.mkdtemp(prefix="anim_")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else await p.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await pg.goto("file://" + f); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getAnimations().forEach(a=>a.pause())")
        n = int(round(total * FPS))
        for i in range(n):
            await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={i * 1000 / FPS})"); await pg.evaluate(RAF2)
            await pg.screenshot(path=os.path.join(frames, f"f{i:05d}.jpg"), type="jpeg", quality=92)
        await pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={spec.get('cover_at', 1.5) * 1000})"); await pg.evaluate(RAF2)
        await pg.screenshot(path=os.path.join(d, "cover.jpg"), type="jpeg", quality=92)
        await b.close()
    # audio: music bed + narration clips placed at scene starts
    no_music = spec.get("music") in (None, "none", False)
    if no_music:
        music = os.path.join(frames, "silence.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{total:.3f}", music], check=True)
    else:
        music = make_track(spec.get("music", "soft_lofi"), total, os.path.join(frames, "music.wav"), spec.get("music_seed", 7))
    inputs, filt, t = ["-i", music], [], 0.0
    voice_labels = []
    for sc in spec["scenes"]:
        if sc.get("audio"):
            k = len(inputs) // 2 + 1
            inputs += ["-i", sc["audio"]]
            ms = int((t + sc.get("vo_offset", .25)) * 1000)
            filt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
            voice_labels.append(f"[v{k}]")
        t += sc["dur"]
    if spec.get("voice"):
        k = len(inputs) // 2 + 1
        inputs += ["-i", spec["voice"]]
        ms = int(spec.get("voice_offset", .3) * 1000)
        filt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
        voice_labels.append(f"[v{k}]")
    if voice_labels:
        filt.append(f"{''.join(voice_labels)}amix=inputs={len(voice_labels)}:normalize=0,volume=1.0[vo]")
        filt.append(f"[1:a]aresample=48000,volume={0 if no_music else 0.16}[bed]")
        filt.append("[bed][vo]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    else:
        filt.append("[1:a]aresample=48000[a]" if no_music else "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    out = os.path.join(d, "reel.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.jpg"), *inputs,
                    "-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                    "-r", str(FPS), "-g", "60", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(frames); os.remove(f)
    print(spec["slug"], f"{total:.1f}s", os.path.getsize(out) // 1024, "KB", ("voice" if voice_labels else "NO VOICE") + (" no music" if no_music else " + music"))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
