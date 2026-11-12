"""Shared helpers for the pipeline tests (stdlib only: `python3 -m unittest discover tests`)."""
import importlib.util, json, os, re, subprocess, sys, warnings

warnings.simplefilter("ignore", ResourceWarning)   # short-lived temp files in tests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "youtube-edit", "scripts")


def load(name):
    """Import a pipeline script as a module without running its main()."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *map(str, args)],
                          capture_output=True, text=True)


def words(text, start=0.0, each=0.25, gap=0.05, pauses=None):
    """'a b c' -> word dicts spaced `each`+`gap` apart; pauses={index: extra seconds before it}."""
    out, t = [], start
    for i, w in enumerate(text.split()):
        t += (pauses or {}).get(i, 0.0)
        out.append({"text": w, "start": round(t, 3), "end": round(t + each, 3), "conf": 1.0})
        t += each + gap
    return out


def captions(workdir, ws, cfg=None):
    """Run captions.py on words + a captions block; return (caps, style, srt text)."""
    json.dump(ws, open(os.path.join(workdir, "words_cut.json"), "w"))
    json.dump({"captions": cfg or {}}, open(os.path.join(workdir, "overlays.json"), "w"))
    r = run("captions.py", workdir)
    assert r.returncode == 0, r.stderr
    js = open(os.path.join(workdir, "public", "captions.js")).read()
    caps = json.loads(re.search(r"window\.__CAPS = (\[.*?\]);\n", js, re.S).group(1))
    style = json.loads(re.search(r"window\.__CAPS_STYLE = (.*?);", js).group(1))
    return caps, style, open(os.path.join(workdir, "captions.srt")).read()
