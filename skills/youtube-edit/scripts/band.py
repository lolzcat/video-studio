#!/usr/bin/env python3
"""Header-band short: build the HyperFrames composition and the picture from overlays.json.

Usage: band.py <workdir>

For the header-band layout (SKILL.md → Intake): source_916.mp4 has a solid brand band at
y 0–420 and the speaker below it. This writes, from <workdir>/overlays.json:
  public/index.html        band kicker (logo or text) + accent rule + one headline line at a
                           time + full-region stat cutaways + name tag + captions (K1/K2)
  public/input-video.mp4   cut.mp4 with any B-roll laid over the speaker region
  public/fonts, brand, vendor   copied assets
Then run timing.py export (writes timings.js, syncs card-host data-start/duration) and render.

overlays.json additions (alongside the usual canvas/face_box/cards/captions):
  "brand": {
    "band": "#0A0A0A", "text": "#FFFFFF", "accent": "#C9A84C",
    "head_font": {"family": "Bebas Neue", "file": "/abs/BebasNeue-Regular.ttf", "weight": 400},
    "cap_font":  {"family": "DM Sans", "file": "/abs/DMSans.ttf", "weight": 700},
    "kicker": {"image": "/abs/logo.png", "width": 430}      # or {"text": "WIMBLEDON FAQ"}
  },
  "cards": [
    {"id": "t0", "kind": "title", "text": "Our job: never lose *money*"},   # K2: one static title, whole clip
    {"id": "c1", "start": 0.1, "end": 2.4, "text": "Never lose *money*"},          # kind "line": swapping headlines (pre-K2)
    {"id": "s1", "kind": "stat", "start": 9.0, "end": 11.4, "text": "3–5×", "sub": "In 4–6 years"},
    {"id": "n1", "kind": "tag", "start": 20.0, "end": 21.6, "text": "Aaron Darr", "sub": "Lead Edge Capital"},
                                        # tag = name line in the band slot (one band line at a time)
    {"id": "s2", "kind": "stat", "kicker": "The goal", "text": "3–5×", "sub": "in *4–6 years*", ...}
  ],                                    # *word* = accent colour; "font_px" overrides 104 for a line
  "broll": [{"file": "/abs/diesel.mp4", "start": 2.6, "end": 4.3, "src_in": 0.0}]
                                        # edges snap to jump cuts within 0.3s; min 1.2s
Short gaps between headline lines are filled by holding the previous line. In sound_plan.json an
SFX with "broll": N (+ "offset") is re-timed to that insert's start.
                                        # covers the speaker region (y 420–1920), 1-frame fades
Missing bboxes are filled in so check_plan.py can check them.
"""
import html, json, os, re, shutil, subprocess, sys

REGION = [0, 420, 1080, 1500]   # speaker region under the band
LINE_BOX = [60, 300, 960, 116]
TAG_BOX = [48, 440, 600, 72]   # one-line name label over the video, clear of the head


def fps_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip() or "30/1"
    n, d = r.split("/")
    return round(float(n) / float(d or 1))


def dur_of(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                 "csv=p=0", path], capture_output=True, text=True).stdout.strip())


def cut_times(workdir):
    """Jump-cut times on the cut timeline (from edl_tight.json, else edl.json)."""
    for n in ("edl_tight.json", "edl.json"):
        p = os.path.join(workdir, n)
        if os.path.exists(p):
            t, out = 0.0, []
            for sgm in json.load(open(p))["segments"]:
                t += sgm["out"] - sgm["in"]
                out.append(round(t, 3))
            return out[:-1]
    return []


def snap_broll(ov, cuts, dur):
    """A B-roll edge within 0.3s of a jump cut moves onto it (no flash frames of a new framing);
    every insert lasts >= 1.2s (G1)."""
    for b in ov.get("broll", []):
        for k in ("start", "end"):
            near = min(cuts, key=lambda c: abs(c - b[k]), default=None)
            if near is not None and abs(near - b[k]) <= 0.3:
                b[k] = near
        if b["end"] - b["start"] < 1.2:   # stretch to a nearby cut, else exactly 1.2s
            near = [c for c in cuts if b["start"] + 1.2 <= c <= b["start"] + 1.6]
            b["end"] = round(min(near[0] if near else b["start"] + 1.2, dur), 3)


def fill_gaps(cards, dur):
    """Headline lines hold until the next one when the gap is short (an empty band reads as a
    dropped line); the last line holds to the end."""
    lines = sorted([c for c in cards if c.get("kind", "line") in ("line", "tag") and not c.get("persistent")],
                   key=lambda c: c["start"])
    for a, b in zip(lines, lines[1:]):
        if 0 < b["start"] - a["end"] <= 1.6:
            a["end"] = b["start"]
    if lines and dur - lines[-1]["end"] <= 1.6:
        lines[-1]["end"] = dur


def keyed_logo(src, pub):
    """Logos exported on black: key the black to transparency so no box shows on the band."""
    os.makedirs(os.path.join(pub, "brand"), exist_ok=True)
    rel = os.path.join("brand", os.path.splitext(os.path.basename(src))[0] + "_keyed.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                    "format=rgba,colorkey=0x000000:0.12:0.08", "-frames:v", "1", os.path.join(pub, rel)], check=True)
    return rel


def rich(text):
    """'Never lose *money*' -> escaped HTML with accent spans."""
    out, parts = [], re.split(r"(\*[^*]+\*)", text)
    for p in parts:
        if p.startswith("*") and p.endswith("*"):
            out.append(f'<span class="accent">{html.escape(p[1:-1])}</span>')
        else:
            out.append(html.escape(p))
    return "".join(out)


def stage(src, pub, sub):
    os.makedirs(os.path.join(pub, sub), exist_ok=True)
    dst = os.path.join(sub, os.path.basename(src))
    shutil.copy2(src, os.path.join(pub, dst))
    return dst


def picture(workdir, ov):
    cut = os.path.join(workdir, "cut.mp4")
    out = os.path.join(workdir, "public", "input-video.mp4")
    broll = ov.get("broll", [])
    if not broll:
        shutil.copy2(cut, out)
        return
    x, y, w, h = REGION
    args, chain, last = ["ffmpeg", "-v", "error", "-y", "-i", cut], [], "[0:v]"
    for i, b in enumerate(broll, 1):
        args += ["-i", b["file"]]
        d = b["end"] - b["start"]
        s_in = b.get("src_in", 0.0)
        chain.append(
            f"[{i}:v]trim={s_in}:{s_in + d + 0.05},setpts=PTS-STARTPTS+{b['start']}/TB,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuva420p,"
            f"fade=t=in:st={b['start']}:d=0.04:alpha=1,fade=t=out:st={b['end'] - 0.04}:d=0.04:alpha=1[b{i}]")
        chain.append(f"{last}[b{i}]overlay={x}:{y}:eof_action=pass:enable='between(t,{b['start']},{b['end']})'[v{i}]")
        last = f"[v{i}]"
    args += ["-filter_complex", ";".join(chain), "-map", last, "-map", "0:a", "-c:v", "libx264", "-crf", "16",
             "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out]
    subprocess.run(args, check=True)


def main():
    workdir = os.path.abspath(sys.argv[1])
    pub = os.path.join(workdir, "public")
    ovp = os.path.join(workdir, "overlays.json")
    ov = json.load(open(ovp))
    br = ov["brand"]
    dur = round(dur_of(os.path.join(workdir, "cut.mp4")), 3)
    fps = fps_of(os.path.join(workdir, "cut.mp4"))  # render at the source rate: 24 -> 30 judders
    os.makedirs(pub, exist_ok=True)

    hf, cf = br["head_font"], br["cap_font"]
    hfile, cfile = stage(hf["file"], pub, "fonts"), stage(cf["file"], pub, "fonts")
    gsap = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "vendor", "gsap.min.js")
    if not os.path.exists(gsap):
        sys.exit(f"missing {gsap}")
    stage(gsap, pub, "vendor")
    kick = br.get("kicker", {})
    if kick.get("image"):
        kimg = keyed_logo(kick["image"], pub)
        kicker_html = f'<img src="{kimg}" style="width:{int(kick.get("width", 430))}px" alt="">'
    else:
        kicker_html = html.escape(kick.get("text", ""))

    snap_broll(ov, cut_times(workdir), dur)
    fill_gaps(ov["cards"], dur)
    sp = os.path.join(workdir, "sound_plan.json")   # SFX tied to a B-roll insert follow it
    if os.path.exists(sp):
        plan = json.load(open(sp))
        for x in plan.get("sfx", []):
            if x.get("broll"):
                x["at"] = round(ov["broll"][x["broll"] - 1]["start"] + x.get("offset", 0.0), 3)
        json.dump(plan, open(sp, "w"), indent=1)

    # fill boxes for check_plan
    for c in ov["cards"]:
        kind = c.get("kind", "line")
        if kind in ("line", "title"):
            c.setdefault("bbox", LINE_BOX)
            c.setdefault("font_px", 104)
            if kind == "title":
                c.update(persistent=True, start=0, end=dur)
        elif kind == "stat":
            c.setdefault("bbox", REGION)
            c.setdefault("font_px", 64)
        elif kind == "tag":
            c["bbox"] = TAG_BOX
            c["font_px"] = 40
    json.dump(ov, open(ovp, "w"), indent=1, ensure_ascii=False)

    hosts = []
    for c in ov["cards"]:
        kind, cid = c.get("kind", "line"), c["id"]
        if c.get("persistent") and kind != "title":
            continue
        attrs = (f'class="card-host clip" data-card-id="{cid}" data-start="{c["start"]}" '
                 f'data-duration="{round(c["end"] - c["start"], 3)}" data-track-index="3" '
                 'style="visibility:hidden;opacity:0;"')
        if kind in ("line", "title"):
            fs = f' style="font-size:{int(c["font_px"])}px"' if c.get("font_px", 104) != 104 else ""
            inner = f'<div class="slot"><div class="line" id="{cid}-line"{fs}>{rich(c["text"])}</div></div>'
        elif kind == "stat":
            kk = f'<div class="kick">{rich(c["kicker"])}</div>' if c.get("kicker") else ""
            inner = (f'<div class="stat" id="{cid}-stat">{kk}<div class="big" id="{cid}-big">{rich(c["text"])}</div>'
                     f'<div class="sub" id="{cid}-sub">{rich(c.get("sub", ""))}</div></div>')
        else:  # name tag: one compact label over the video (K2: the band holds only the title)
            inner = (f'<div class="tag" id="{cid}-tag"><span class="name">{rich(c["text"])}</span>'
                     f'<span class="org">{html.escape(c.get("sub", ""))}</span></div>')
        hosts.append(f'      <div {attrs}>\n        <div class="card" data-card-id="{cid}" data-kind="{kind}">{inner}</div>\n      </div>')

    kinds = {c["id"]: c.get("kind", "line") for c in ov["cards"]
             if not c.get("persistent") or c.get("kind") == "title"}
    caps_y = int(ov.get("captions", {}).get("y", 1410))
    page = TEMPLATE.format(
        dur=dur, fps=fps, band=br["band"], text=br["text"], accent=br["accent"],
        hfam=hf["family"], hfile=hfile, hw=hf.get("weight", 400),
        cfam=cf["family"], cfile=cfile, cw=cf.get("weight", 700),
        kicker=kicker_html, hosts="\n".join(hosts), kinds=json.dumps(kinds), caps_y=caps_y,
        end_beat=round(max(0.0, dur - 0.55), 3))
    page = page.replace("__CAPS_LAYER__", open(os.path.join(os.path.dirname(gsap), "caps-layer.js")).read())
    open(os.path.join(pub, "index.html"), "w").write(page)
    picture(workdir, ov)
    print(f"band composition: {len(hosts)} cards, {len(ov.get('broll', []))} B-roll, {dur}s -> {pub}/index.html")


TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <style>
      @font-face {{ font-family: "{hfam}"; src: url("{hfile}"); font-weight: {hw}; font-display: block; }}
      @font-face {{ font-family: "{cfam}"; src: url("{cfile}"); font-weight: 100 900; font-display: block; }}
      :root {{ --band: {band}; --text: {text}; --accent-0: {accent}; }}
      * {{ box-sizing: border-box; }}
      html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #000; }}
      #stage {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
      .video-wrapper {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; }}
      .video-wrapper video {{ width: 100%; height: 100%; object-fit: cover; }}
      .head-host {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; pointer-events: none; }}
      .kicker {{ position: absolute; left: 60px; right: 60px; top: 232px; height: 64px; display: flex;
                align-items: center; justify-content: center; color: var(--accent-0);
                font-family: "{hfam}", sans-serif; font-size: 44px; letter-spacing: 0.14em; }}
      .rule {{ position: absolute; left: 0; top: 414px; width: 1080px; height: 6px; background: var(--accent-0); transform-origin: 0 50%; }}
      .card-host {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; pointer-events: none; overflow: hidden; }}
      .card-host .card {{ position: relative; width: 100%; height: 100%; }}
      .card .slot {{ position: absolute; left: 60px; right: 60px; top: 298px; height: 116px; overflow: hidden; }}
      .card .line {{ position: absolute; left: 0; right: 0; top: 0; height: 116px; display: block; text-align: center;
                    white-space: pre; font-family: "{hfam}", sans-serif; font-weight: {hw}; font-size: 104px;
                    line-height: 122px; letter-spacing: 0.03em; color: var(--text); text-transform: uppercase; }}
      .card .accent {{ color: var(--accent-0); }}
      .card .stat {{ position: absolute; left: 0; top: 420px; width: 1080px; height: 1500px; background: var(--band);
                    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
                    padding-bottom: 420px; }}  /* keep the stat above the low captions (K2) */
      .card .stat .big {{ font-family: "{hfam}", sans-serif; font-size: 420px; line-height: 0.9; color: var(--accent-0); letter-spacing: 0.01em; }}
      .card .stat .sub {{ font-family: "{hfam}", sans-serif; font-size: 96px; letter-spacing: 0.08em; color: var(--text); text-transform: uppercase; }}
      .card .stat .kick {{ font-family: "{hfam}", sans-serif; font-size: 72px; letter-spacing: 0.16em; color: var(--text); opacity: 0.8; }}
      .card .stat .sub .accent {{ color: var(--accent-0); }}
      .card .tag {{ position: absolute; left: 48px; top: 440px; height: 72px; padding: 0 26px; display: flex; align-items: center;
                   gap: 16px; background: rgba(10,10,10,0.86); border-left: 6px solid var(--accent-0); border-radius: 6px; white-space: nowrap; }}
      .card .tag .name {{ font-family: "{hfam}", sans-serif; font-size: 48px; letter-spacing: 0.06em; color: var(--text); line-height: 1; }}
      .card .tag .org {{ font-family: "{cfam}", sans-serif; font-weight: 600; font-size: 40px; color: var(--accent-0); }}
      .caps-host {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; pointer-events: none; }}
      .caps-host .cap {{ position: absolute; left: 110px; right: 110px; text-align: center; white-space: nowrap;
                        font-family: "{cfam}", sans-serif; font-weight: {cw}; font-size: 76px; line-height: 1.08;
                        letter-spacing: 0; word-spacing: 0.14em; color: #ffffff; -webkit-text-stroke: 15px #0a0a0a; paint-order: stroke fill;
                        text-shadow: 0 4px 10px rgba(0,0,0,0.75), 0 0 22px rgba(0,0,0,0.45); opacity: 0; }}
      .caps-host .cap .em {{ color: var(--accent-0); }}
      .caps-host .cap.bold {{ font-weight: 900; font-size: 100px; line-height: 1; text-transform: uppercase;
                             letter-spacing: 0.01em; word-spacing: 0; -webkit-text-stroke: 14px #0a0a0a; }}
      .caps-host .cap.bold .w {{ display: inline-block; margin: 0 0.1em; transform-origin: 50% 70%; }}
      .caps-host .cap.bold .w.em {{ font-size: 1.1em; }}   /* bigger in the layout, so it never overlaps */
    </style>
  </head>
  <body>
    <div id="stage" data-composition-id="talking-head-recut" data-start="0" data-duration="{dur}" data-fps="{fps}" data-width="1080" data-height="1920">
      <div class="video-wrapper"><video id="bg-video" src="input-video.mp4" playsinline data-has-audio="true" data-start="0" data-duration="{dur}" data-track-index="1"></video></div>
      <div class="head-host clip" data-start="0" data-duration="{dur}" data-track-index="2">
        <div class="kicker" id="kicker">{kicker}</div>
        <div class="rule" id="rule"></div>
      </div>
{hosts}
      <div id="caps-host" class="caps-host clip" data-start="0" data-duration="{dur}" data-track-index="4"></div>
      <script src="vendor/gsap.min.js"></script>
      <script src="timings.js"></script>
      <script>
        (function () {{
          const q = (t) => Math.round(t * {fps}) / {fps};
          const tl = window.gsap.timeline({{ paused: true }});
          const T = window.__T, KINDS = {kinds};
          const host = (id) => '.card-host[data-card-id="' + id + '"]';
          const el = (id, part) => '.card[data-card-id="' + id + '"] #' + id + "-" + part;
          tl.set("#kicker", {{ opacity: 1 }}, 0);   // whole band on frame 0 (first frame = thumbnail)
          tl.set("#rule", {{ scaleX: 1 }}, 0);
          Object.keys(KINDS).forEach(function (id) {{
            const s = T[id].start, e = T[id].end, k = KINDS[id];
            tl.set(host(id), {{ visibility: "visible", opacity: 1 }}, q(s));
            tl.set(host(id), {{ opacity: 0, visibility: "hidden" }}, q(e));
            if (k === "title") {{   // K2: one static title, rises with the rule, holds to the end
              tl.set(el(id, "line"), {{ yPercent: 0, opacity: 1 }}, 0);   // on frame 0 (first frame = thumbnail)
            }} else if (k === "line") {{   // rises out of the accent rule, sinks out (STYLE L3)
              tl.fromTo(el(id, "line"), {{ yPercent: 100, opacity: 0 }}, {{ yPercent: 0, opacity: 1, duration: 0.24, ease: "power3.out" }}, q(s));
              if (e < {dur} - 0.05) tl.to(el(id, "line"), {{ yPercent: -60, opacity: 0, duration: 0.16, ease: "power2.in" }}, q(e - 0.16));
            }} else if (k === "stat") {{
              tl.fromTo(el(id, "stat"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.14, ease: "power2.out" }}, q(s));
              tl.fromTo(el(id, "big"), {{ scale: 0.86, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "power3.out" }}, q(s + 0.04));
              tl.fromTo(el(id, "sub"), {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.24, ease: "power3.out" }}, q(s + 0.22));
              tl.to(el(id, "stat"), {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, q(e - 0.16));
            }} else {{
              tl.fromTo(el(id, "tag"), {{ x: -40, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.26, ease: "power3.out" }}, q(s));
              tl.to(el(id, "tag"), {{ x: -20, opacity: 0, duration: 0.18, ease: "power2.in" }}, q(e - 0.18));
            }}
          }});
          tl.to("#rule", {{ scaleY: 2.2, duration: 0.16, yoyo: true, repeat: 1, ease: "power2.out" }}, q({end_beat}));
          window.__timelines = window.__timelines || {{}};
          window.__timelines["talking-head-recut"] = tl;
        }})();
      </script>
      <script src="captions.js"></script>
      <script>window.__CAPS_CFG = {{ fps: {fps}, y: {caps_y}, room: 860, min: 62 }};</script>
      <script>  /* K1/K2 captions (assets/vendor/caps-layer.js, inlined: the renderer skips external scripts added late) */
__CAPS_LAYER__
      </script>
    </div>
  </body>
</html>
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main()
