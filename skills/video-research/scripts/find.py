#!/usr/bin/env python3
"""Discover reference videos worth studying, ranked by how hard they over-performed.

Usage:
  find.py youtube  "<query>"   [--n 15] [--days 90] [--out cands.json]
  find.py bilibili "<中文 query>" [--n 20] [--days 60] [--out cands.json]
  find.py bilibili-rank [tech|life|knowledge|all] [--n 20] [--out cands.json]

Scores:
  vpd       views per day since upload (momentum)
  outlier   YouTube: views / channel subscribers (a small channel's video that took
            off = the IDEA worked, not the channel). >1 is strong, >5 is exceptional.
  save      Bilibili: favourites / plays (save-worthy = tutorial value), likes / plays
Prints a table and writes JSON (default: ./candidates.json).
"""
import json, re, subprocess, sys, time, urllib.parse, urllib.request
from http.cookiejar import CookieJar

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130 Safari/537.36")
BILI_RANK = {"all": 0, "tech": 188, "knowledge": 36, "life": 160}


def arg(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def age_days(upload_ts):
    return max(1.0, (time.time() - upload_ts) / 86400)


def youtube(query, n, days):
    out = subprocess.run(["yt-dlp", "--no-warnings", "--skip-download", "--dump-json",
                          f"ytsearchdate{n * 2}:{query}" if days <= 30 else f"ytsearch{n * 2}:{query}"],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        try:
            v = json.loads(line)
        except json.JSONDecodeError:
            continue
        ud = v.get("upload_date")
        ts = time.mktime(time.strptime(ud, "%Y%m%d")) if ud else time.time()
        if age_days(ts) > days:
            continue
        views, subs = v.get("view_count") or 0, v.get("channel_follower_count") or 0
        rows.append({"platform": "youtube", "id": v["id"], "url": v.get("webpage_url"),
                     "title": v.get("title"), "channel": v.get("channel"), "views": views,
                     "subs": subs, "duration": v.get("duration"), "upload_date": ud,
                     "vpd": round(views / age_days(ts)), "outlier": round(views / subs, 2) if subs else None,
                     "short": (v.get("duration") or 0) <= 60})
    rows.sort(key=lambda r: ((r["outlier"] or 0), r["vpd"]), reverse=True)
    return rows[:n]


def bili_opener():
    jar = CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA), ("Referer", "https://www.bilibili.com/")]
    op.open("https://www.bilibili.com/", timeout=20).read()  # anonymous buvid cookies
    return op


def bili_row(v, plays, pub_ts, dur):
    return {"platform": "bilibili", "id": v["bvid"], "url": f"https://www.bilibili.com/video/{v['bvid']}",
            "title": re.sub("<[^>]+>", "", v["title"]), "channel": v.get("author") or v.get("owner", {}).get("name"),
            "views": plays, "duration": dur, "upload_date": time.strftime("%Y%m%d", time.localtime(pub_ts)),
            "vpd": round(plays / age_days(pub_ts)),
            "save": round((v.get("favorites") or v.get("stat", {}).get("favorite", 0)) / plays, 4) if plays else 0,
            "like": round((v.get("like") or v.get("stat", {}).get("like", 0)) / plays, 4) if plays else 0}


def bilibili(query, n, days):
    op, now = bili_opener(), int(time.time())
    q = urllib.parse.urlencode({"search_type": "video", "keyword": query, "order": "click", "page": 1,
                                "pubtime_begin_s": now - days * 86400, "pubtime_end_s": now})
    d = json.loads(op.open("https://api.bilibili.com/x/web-interface/search/type?" + q, timeout=20).read())
    rows = []
    for v in (d.get("data") or {}).get("result") or []:
        mm, _, ss = str(v.get("duration", "0:0")).partition(":")
        rows.append(bili_row(v, int(v.get("play") or 0), int(v.get("pubdate") or now),
                             int(mm or 0) * 60 + int(ss or 0)))
    rows.sort(key=lambda r: r["vpd"], reverse=True)
    return rows[:n]


def bilibili_rank(cat, n):
    op = bili_opener()
    d = json.loads(op.open(f"https://api.bilibili.com/x/web-interface/ranking/v2?rid={BILI_RANK[cat]}&type=all",
                           timeout=20).read())
    rows = [bili_row(v, v["stat"]["view"], v["pubdate"], v["duration"]) for v in (d.get("data") or {}).get("list", [])]
    return rows[:n]


def main():
    mode = sys.argv[1]
    out = arg("--out", "candidates.json")
    if mode == "youtube":
        rows = youtube(sys.argv[2], arg("--n", 15), arg("--days", 90))
    elif mode == "bilibili":
        rows = bilibili(sys.argv[2], arg("--n", 20), arg("--days", 60))
    elif mode == "bilibili-rank":
        cat = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "tech"
        rows = bilibili_rank(cat, arg("--n", 20))
    else:
        sys.exit(__doc__)
    json.dump(rows, open(out, "w"), ensure_ascii=False, indent=1)
    for r in rows:
        if r["platform"] == "youtube":
            extra = f"outlier {r['outlier']}x" if r.get("outlier") is not None else "outlier ?"
        else:
            extra = f"save {r.get('save', 0):.1%}"
        print(f"{r['vpd']:>9,}/day  {r['views']:>10,} views  {extra:<14} {r['duration'] or 0:>5}s  "
              f"{r['upload_date']}  {r['title'][:60]}  {r['url']}")
    print(f"{len(rows)} candidates -> {out}")


if __name__ == "__main__":
    main()
