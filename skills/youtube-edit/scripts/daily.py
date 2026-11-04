#!/usr/bin/env python3
"""Daily mode: one day's recording becomes three shorts, with a running scoreboard.

Series state lives in ~/Movies/youtube-edit/series/<series>/series.json.

  daily.py init  <series> --days 180 [--labels sent,replies,booked]
      Start a series. The labels are the scoreboard counters (cumulative).
  daily.py new   <series> [--date YYYY-MM-DD]
      Open the next day: creates day-NNN/ with raw/{episode,event,dash}/ drop folders and
      three edit folders (episode/, event/, dash/), each with a script.md stub for its format.
  daily.py score <series> [--day N] --sent 52 --replies 1 --booked 0
      Record TODAY's numbers (not totals). Totals are recomputed; writes day-NNN/score.json.
  daily.py prep  <series> [--day N]
      For each slot with footage in raw/<slot>/: transcribe every file into
      <slot>/takes/tNN/ and print durations + first lines, ready for the paper edit.
  daily.py scoreboard <series> <workdir>/public [--day N]
      Write scoreboard.js (window.__SCORE: day, total days, labels, totals before and after
      today) for the scoreboard layer (references/scoreboard-snippet.html).
  daily.py log   <series> [--day N] --slot episode --platform instagram --url <url>
      Add a posted short to day-NNN/posts.md (views at 24h/72h get filled in later).
  daily.py status <series>
      Days done, totals, posts logged, and which days still need 24h/72h view counts.
"""
import datetime as dt, json, os, re, subprocess, sys

ROOT = os.path.expanduser("~/Movies/youtube-edit/series")
HERE = os.path.dirname(os.path.abspath(__file__))
SLOTS = {
    "episode": ("Day N scoreboard episode", "40–50s", "event (SF1/SF19)",
                "Open on the day's event (send / reply / booking / post going up) → scoreboard ticks → "
                "one line on what happened → one ADHD moment (where the boring work almost died and what "
                "caught it) → end-of-day scoreboard → 'see you tomorrow'."),
    "event": ("event clip", "15–30s", "event (SF19/SF20)",
              "One real moment from today's outreach, shown not told: the send, a reply landing, a booked "
              "slot. Event in second one (SF6), a 'POV: …' or scoreboard label, no talking needed, "
              "privacy blur on every prospect detail (SF18)."),
    "dash": ("dash one-liner", "12–16s", "dash (SF3)",
             "One take in the car: one ADHD or boring-work reframe, a 1s pause after the turn word, "
             "captions in the space above your head, no CTA."),
}


def arg(name, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def sdir(series):
    return os.path.join(ROOT, series)


def load(series):
    p = os.path.join(sdir(series), "series.json")
    if not os.path.exists(p):
        sys.exit(f"no series '{series}' — run: daily.py init {series} --days 180")
    return json.load(open(p))


def save(series, s):
    json.dump(s, open(os.path.join(sdir(series), "series.json"), "w"), indent=1)


def day_dir(series, n):
    return os.path.join(sdir(series), f"day-{n:03d}")


def totals(s, upto):
    t = {k: 0 for k in s["labels"]}
    for d in s["days"]:
        if d["day"] <= upto:
            for k in s["labels"]:
                t[k] += int(d.get("today", {}).get(k, 0))
    return t


def stub(slot, series, n, s):
    title, length, fmt, shape = SLOTS[slot]
    return f"""---
date: {s['days'][-1]['date']}
slug: {series}-day{n:03d}-{slot}
format: short
target_length: {length}
style: short-form-v1.1
series: {series} · day {n}/{s['total_days']}
slot: {slot} ({fmt})
status: stub
---
# {series} · Day {n} · {title}

**Shape:** {shape}

**Scoreboard:** `daily.py scoreboard {series} <this folder>/public` writes the numbers; the
episode shows totals before → after today. Event and dash clips show the current totals static.

## Script + shot list
(fill with /video-script, or write lines straight from the day's footage)

## Teleprompter

## Flags
- Numbers on screen must match the screenshot exactly (SF17). Blur prospect details (SF18).
"""


def cmd_init(series):
    os.makedirs(sdir(series), exist_ok=True)
    p = os.path.join(sdir(series), "series.json")
    if os.path.exists(p):
        sys.exit(f"series '{series}' already exists at {p}")
    labels = arg("--labels", "sent,replies,booked").split(",")
    s = {"name": series, "total_days": arg("--days", 180, int), "labels": labels,
         "started": dt.date.today().isoformat(), "days": []}
    save(series, s)
    print(f"series '{series}': {s['total_days']} days, scoreboard {labels} -> {p}")


def cmd_new(series):
    s = load(series)
    n = (s["days"][-1]["day"] + 1) if s["days"] else 1
    date = arg("--date", dt.date.today().isoformat())
    s["days"].append({"day": n, "date": date, "today": {}, "posts": []})
    save(series, s)
    d = day_dir(series, n)
    for slot in SLOTS:
        os.makedirs(os.path.join(d, "raw", slot), exist_ok=True)
        os.makedirs(os.path.join(d, slot), exist_ok=True)
        open(os.path.join(d, slot, "script.md"), "w").write(stub(slot, series, n, s))
    open(os.path.join(d, "README.md"), "w").write(
        f"# {series} · Day {n}/{s['total_days']} · {date}\n\nDrop today's footage here:\n"
        "- `raw/episode/` — the end-of-day check-in + any screen recording of the day's event\n"
        "- `raw/event/` — screen recordings of outreach moments (sends, replies, bookings)\n"
        "- `raw/dash/` — the car one-liner takes\n\n"
        f"Then: `daily.py score {series} --{' --'.join(l + ' N' for l in s['labels'])}` and "
        f"`daily.py prep {series}`.\n")
    print(f"day {n}/{s['total_days']} opened -> {d}")


def cmd_score(series):
    s = load(series)
    n = arg("--day", s["days"][-1]["day"], int)
    day = next(x for x in s["days"] if x["day"] == n)
    for k in s["labels"]:
        v = arg(f"--{k}")
        if v is not None:
            day["today"][k] = int(v)
    save(series, s)
    before, after = totals(s, n - 1), totals(s, n)
    json.dump({"day": n, "total_days": s["total_days"], "labels": s["labels"], "today": day["today"],
               "before": before, "after": after},
              open(os.path.join(day_dir(series, n), "score.json"), "w"), indent=1)
    print(f"day {n}: today {day['today']} · totals {after}")


def cmd_prep(series):
    s = load(series)
    n = arg("--day", s["days"][-1]["day"], int)
    d = day_dir(series, n)
    for slot in SLOTS:
        files = sorted(f for f in os.listdir(os.path.join(d, "raw", slot))
                       if f.lower().endswith((".mp4", ".mov", ".m4v", ".mkv")))
        if not files:
            print(f"[{slot}] no footage in raw/{slot}/")
            continue
        for i, f in enumerate(files, 1):
            src = os.path.join(d, "raw", slot, f)
            out = os.path.join(d, slot, "takes", f"t{i:02d}")
            if not os.path.exists(os.path.join(out, "transcript.txt")):
                subprocess.run(["python3", os.path.join(HERE, "transcribe.py"), src, out],
                               capture_output=True)
            dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                  "csv=p=0", src], capture_output=True, text=True).stdout.strip()
            first = (open(os.path.join(out, "transcript.txt")).readline().strip()
                     if os.path.exists(os.path.join(out, "transcript.txt")) else "(no transcript)")
            print(f"[{slot}] t{i:02d} {f} · {float(dur or 0):.1f}s · {first[:90]}")


def cmd_scoreboard(series, public):
    s = load(series)
    n = arg("--day", s["days"][-1]["day"], int)
    p = os.path.join(day_dir(series, n), "score.json")
    if not os.path.exists(p):
        sys.exit(f"no numbers for day {n} yet — run: daily.py score {series} --day {n} ...")
    os.makedirs(public, exist_ok=True)
    open(os.path.join(public, "scoreboard.js"), "w").write("window.__SCORE = " + open(p).read() + ";\n")
    print(f"scoreboard for day {n} -> {public}/scoreboard.js")


def cmd_log(series):
    s = load(series)
    n = arg("--day", s["days"][-1]["day"], int)
    day = next(x for x in s["days"] if x["day"] == n)
    post = {"slot": arg("--slot"), "platform": arg("--platform"), "url": arg("--url"),
            "posted": dt.datetime.now().isoformat(timespec="minutes"), "views_24h": None, "views_72h": None}
    day["posts"].append(post)
    save(series, s)
    rows = ["| slot | platform | posted | url | views 24h | views 72h |", "|---|---|---|---|---|---|"]
    rows += [f"| {p['slot']} | {p['platform']} | {p['posted']} | {p['url']} | {p['views_24h'] or ''} | "
             f"{p['views_72h'] or ''} |" for p in day["posts"]]
    open(os.path.join(day_dir(series, n), "posts.md"), "w").write("\n".join(rows) + "\n")
    print(f"logged {post['slot']} on {post['platform']} for day {n}")


def cmd_status(series):
    s = load(series)
    last = s["days"][-1]["day"] if s["days"] else 0
    print(f"{series}: day {last}/{s['total_days']} · totals {totals(s, last)}")
    now = dt.datetime.now()
    for d in s["days"]:
        for p in d["posts"]:
            age = (now - dt.datetime.fromisoformat(p["posted"])).total_seconds() / 3600
            need = [h for h, k in ((24, "views_24h"), (72, "views_72h")) if age >= h and not p[k]]
            if need:
                print(f"  day {d['day']} {p['slot']} on {p['platform']}: needs views at {need}h -> {p['url']}")
        missing = [slot for slot in SLOTS if slot not in {p['slot'] for p in d["posts"]}]
        if missing and d["day"] < last:
            print(f"  day {d['day']}: not posted: {', '.join(missing)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, series = sys.argv[1], sys.argv[2]
    {"init": cmd_init, "new": cmd_new, "score": cmd_score, "prep": cmd_prep, "log": cmd_log,
     "status": cmd_status}.get(cmd, lambda _: None)(series) if cmd != "scoreboard" else cmd_scoreboard(series, sys.argv[3])
    if cmd not in ("init", "new", "score", "prep", "log", "status", "scoreboard"):
        sys.exit(__doc__)
