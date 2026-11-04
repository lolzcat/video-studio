#!/usr/bin/env python3
"""B-roll plan → review → approval → generation → placement (references/broll-prompting.md).

  broll.py review  <workdir>                      write broll-review.md with per-shot cost + total
  broll.py approve <workdir> --shots B1,B3|all --confirm
                                                  mark named shots approved (only after Andrew's yes)
  broll.py queue   <workdir> [--go]               dry run by default: print the exact payloads;
                                                  --go submits approved Oxen shots, once each
  broll.py fetch   <workdir>                      download finished shots into <workdir>/broll/
  broll.py place   <workdir>                      add fetched shots to overlays.json "broll"

<workdir>/broll-plan.json holds the shots (schema in references/broll-prompting.md). Oxen calls go
through the shared helper (OXEN_API_HELPER, default ~/.local/bin/oxen-api.py), which keeps the key
in the macOS Keychain. Higgsfield shots are generated with its MCP tools by Claude, not here.
A prompt edited after approval resets that shot to pending. An uncertain submit is never retried.
"""
import datetime as dt, hashlib, json, os, subprocess, sys, tempfile

HELPER = os.environ.get("OXEN_API_HELPER", os.path.expanduser("~/.local/bin/oxen-api.py"))
CACHE = os.path.expanduser("~/.cache/video-studio/oxen-models.json")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load(workdir):
    p = os.path.join(workdir, "broll-plan.json")
    if not os.path.exists(p):
        sys.exit(f"no {p} — write the plan first (references/broll-prompting.md)")
    return p, json.load(open(p))


def save(p, plan):
    json.dump(plan, open(p, "w"), indent=1, ensure_ascii=False)


def phash(s):
    return hashlib.sha256(json.dumps([s.get(k) for k in ("prompt", "model", "seconds", "resolution",
                                                          "aspect_ratio", "provider")]).encode()).hexdigest()[:16]


def generated(plan):
    return [s for s in plan["shots"] if s.get("route") == "GENERATED"]


def oxen(*args, output=None):
    cmd = ["python3", HELPER, *args] + (["--output", output] if output else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def oxen_prices():
    if not os.path.exists(CACHE) or (dt.datetime.now().timestamp() - os.path.getmtime(CACHE)) > 86400:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        code, _, err = oxen("GET", "/models", output=CACHE)
        if code:
            print(f"(could not refresh Oxen prices: {err.strip()[:120]})")
    try:
        data = json.load(open(CACHE))
        return {m["id"]: m.get("pricing") or {} for m in data.get("data", data)}
    except Exception:
        return {}


def cost(s, prices):
    if s.get("provider", "oxen") == "higgsfield":
        return None, f"{s['credits']} credits" if s.get("credits") else "quote credits first"
    p = prices.get(s.get("model"), {})
    by_res = p.get("cost_per_second_by_resolution") or {}
    rate = by_res.get(s.get("resolution")) or p.get("cost_per_second")
    if rate is None:
        return None, "price unknown"
    usd = rate * float(s.get("seconds", 5))
    return usd, f"${usd:.2f}"


def sync_approvals(plan):
    """Approval is tied to the exact prompt/model/settings it was given for."""
    for s in generated(plan):
        if s.get("approval") == "approved" and s.get("approved_hash") != phash(s):
            s["approval"], s["approved_hash"] = "pending", None
            print(f"{s['id']}: changed since approval -> pending")


def cmd_review(workdir):
    p, plan = load(workdir)
    sync_approvals(plan)
    prices = oxen_prices() if any(s.get("provider", "oxen") == "oxen" for s in generated(plan)) else {}
    rows = ["| shot | time | line | route | why | model | sec | cost | approval |", "|---|---|---|---|---|---|---|---|---|"]
    total, unknown = 0.0, 0
    for s in plan["shots"]:
        usd, label = cost(s, prices) if s.get("route") == "GENERATED" else (0.0, "—")
        total += usd or 0.0
        unknown += usd is None
        rows.append(f"| {s['id']} | {s.get('start', '')}–{s.get('end', '')} | {s.get('line', '')} | {s.get('route')} | "
                    f"{s.get('why', '')} | {s.get('model', '—') if s.get('route') == 'GENERATED' else '—'} | "
                    f"{s.get('seconds', '') if s.get('route') == 'GENERATED' else ''} | {label} | "
                    f"{s.get('approval', '—') if s.get('route') == 'GENERATED' else '—'} |")
    out = [f"# B-roll review — {os.path.basename(os.path.abspath(workdir))}", "", *rows, "",
           f"**Generated shots: {len(generated(plan))} · total ≈ ${total:.2f}"
           + (f" + {unknown} still to price" if unknown else "") + "** (nothing is spent until approved)", ""]
    for s in generated(plan):
        out += [f"## {s['id']} — {s.get('line', '')}", f"- provider/model: {s.get('provider', 'oxen')} / {s.get('model')}, "
                f"{s.get('seconds')}s {s.get('resolution')} {s.get('aspect_ratio')}; use from {s.get('use_from', 0)}s",
                f"- realism: {s.get('realism', '—')}", "", "```text", s.get("prompt", ""), "```", ""]
    open(os.path.join(workdir, "broll-review.md"), "w").write("\n".join(out))
    save(p, plan)
    print("\n".join(rows))
    print(f"\n{len(generated(plan))} generated shot(s), total ≈ ${total:.2f}" + (f" + {unknown} unpriced" if unknown else "")
          + f" -> {workdir}/broll-review.md")


def cmd_approve(workdir):
    if "--confirm" not in sys.argv:
        sys.exit("approve needs --confirm (only after Andrew approved these shots in chat)")
    p, plan = load(workdir)
    want = arg("--shots", "")
    ids = {s["id"] for s in generated(plan)} if want == "all" else set(want.split(","))
    for s in generated(plan):
        if s["id"] in ids:
            s.update(approval="approved", approved_hash=phash(s), approved_at=dt.datetime.now().isoformat(timespec="seconds"))
    missing = ids - {s["id"] for s in generated(plan)}
    save(p, plan)
    print(f"approved: {', '.join(sorted(ids - missing)) or 'none'}" + (f"; not generated shots: {', '.join(sorted(missing))}" if missing else ""))


def cmd_queue(workdir):
    p, plan = load(workdir)
    sync_approvals(plan)
    go = "--go" in sys.argv
    todo = [s for s in generated(plan) if s.get("approval") == "approved" and s.get("provider", "oxen") == "oxen"
            and not s.get("job") and s.get("status") != "submit_uncertain"]
    if not todo:
        print("nothing to queue (needs route GENERATED, provider oxen, approval approved, no job yet)")
    for s in todo:
        payload = {"model": s["model"], "prompt": s["prompt"], "duration": int(s.get("seconds", 5)),
                   "resolution": s.get("resolution"), "aspect_ratio": s.get("aspect_ratio"), "num_generations": 1,
                   "target_repo": "playground", "target_directory": os.path.basename(os.path.abspath(workdir)) + "-broll"}
        payload = {k: v for k, v in payload.items() if v is not None}
        if not go:
            print(f"[dry run] {s['id']}: POST /queue {json.dumps(payload, ensure_ascii=False)[:600]}")
            continue
        fd, req = tempfile.mkstemp(suffix=".json")
        os.write(fd, json.dumps(payload).encode()); os.close(fd)
        out = req.replace(".json", "_out.json")
        code, _, err = oxen("POST", "/queue", "--json-file", req, output=out)
        try:
            gid = json.load(open(out))["generations"][0]["generation_id"]
            s.update(job=gid, status="queued", queued_at=dt.datetime.now().isoformat(timespec="seconds"))
            print(f"{s['id']}: queued {gid}")
        except Exception:
            s["status"] = "submit_uncertain"   # may have been billed: never retry blindly
            print(f"{s['id']}: submit uncertain ({err.strip()[:160]}) — check Oxen before trying again")
        finally:
            for f in (req, out):
                if os.path.exists(f):
                    os.remove(f)
        save(p, plan)
    if not go and todo:
        print("dry run only — add --go to submit (spends money)")
    save(p, plan)


def cmd_fetch(workdir):
    p, plan = load(workdir)
    os.makedirs(os.path.join(workdir, "broll"), exist_ok=True)
    for s in generated(plan):
        if not s.get("job") or s.get("file"):
            continue
        code, out, err = oxen("GET", f"/queue/{s['job']}")
        try:
            g = json.loads(out)
            g = g.get("generation", g)
        except Exception:
            print(f"{s['id']}: could not read status ({err.strip()[:120]})")
            continue
        s["status"] = g.get("status")
        if g.get("status") == "succeeded" and g.get("result_url"):
            dst = os.path.join(workdir, "broll", f"{s['id']}.mp4")
            subprocess.run(["curl", "-sL", "-o", dst, g["result_url"]], check=True)
            s["file"] = dst
            print(f"{s['id']}: downloaded -> {dst}  (look at it before placing: hands, text, subject)")
        else:
            print(f"{s['id']}: {g.get('status')} {g.get('error_message') or ''}")
    save(p, plan)


def cmd_place(workdir):
    p, plan = load(workdir)
    ovp = os.path.join(workdir, "overlays.json")
    ov = json.load(open(ovp))
    planned = [{"file": s["file"], "start": s["start"], "end": s["end"], "src_in": s.get("use_from", 0.0), "plan_id": s["id"]}
               for s in plan["shots"] if s.get("route") == "GENERATED" and s.get("file") and s.get("start") is not None]
    overlaps = lambda b: any(b["start"] < q["end"] and b["end"] > q["start"] for q in planned)
    # hand-placed inserts survive unless a planned shot now covers the same moment
    keep = [b for b in ov.get("broll", []) if not b.get("plan_id") and not overlaps(b)] + planned
    ov["broll"] = sorted(keep, key=lambda b: b["start"])
    json.dump(ov, open(ovp, "w"), indent=1, ensure_ascii=False)
    print(f"{len(ov['broll'])} B-roll insert(s) in overlays.json — run band.py (snaps to cuts) and timing.py export")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    {"review": cmd_review, "approve": cmd_approve, "queue": cmd_queue, "fetch": cmd_fetch, "place": cmd_place}.get(
        sys.argv[1], lambda _: sys.exit(__doc__))(sys.argv[2])
