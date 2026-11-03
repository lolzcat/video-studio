#!/usr/bin/env python3
"""Final audio mix: voice + ducked music beds + SFX, loudness-normalised.

Usage: mix.py <picture.mp4> <voice.mp4> <sound_plan.json> <out.mp4>
  picture.mp4  video to use (HyperFrames render, or the cut itself)
  voice.mp4    file whose audio is the dialogue track (normally cut.mp4)

sound_plan.json (all times on the CUT timeline, seconds):
{
  "music": [{"file": "/abs/hook.mp3", "start": 0, "end": 12.5, "gain_db": -24, "fade": 1.0}],
  "sfx":   [{"file": "/abs/pop.wav", "at": 3.42, "gain_db": -12}],
  "duck": true
}
Music is side-chain ducked under the voice when "duck" is true (default).
Output is normalised to -14 LUFS integrated, -1.5 dBTP (YouTube target).
Also writes pre-normalisation stems to <out dir>/stems/{rest,sfx}.wav for sync_sheet.py.
"""
import json, os, re, subprocess, sys, tempfile


def main():
    picture, voice, plan_path, out = sys.argv[1:5]
    plan = json.load(open(plan_path))
    inputs = ["-i", picture, "-i", voice]
    parts, n = [], 2
    parts.append("[1:a]aresample=48000,asplit=2[voice][sc]")
    music_labels, sfx_labels = [], []
    for i, m in enumerate(plan.get("music", [])):
        inputs += ["-stream_loop", "-1", "-i", m["file"]]
        d, f = m["end"] - m["start"], m.get("fade", 1.0)
        parts.append(f"[{n}:a]aresample=48000,atrim=0:{d},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={f},afade=t=out:st={max(0, d - f)}:d={f},"
                     f"volume={m.get('gain_db', -24)}dB,adelay={int(m['start'] * 1000)}:all=1[m{i}]")
        music_labels.append(f"[m{i}]")
        n += 1
    for i, s in enumerate(plan.get("sfx", [])):
        inputs += ["-i", s["file"]]
        # Trim the file's leading silence so "at" is when the transient sounds, not
        # when the file starts (generated SFX often carry ~100 ms of silence).
        parts.append(f"[{n}:a]aresample=48000,silenceremove=start_periods=1:start_threshold=-45dB,"
                     f"volume={s.get('gain_db', -12)}dB,"
                     f"adelay={int(s['at'] * 1000)}:all=1[s{i}]")
        sfx_labels.append(f"[s{i}]")
        n += 1

    bed = None
    if music_labels:
        parts.append("".join(music_labels) + f"amix=inputs={len(music_labels)}:normalize=0[mus]")
        if plan.get("duck", True):
            parts.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[bed]")
        else:
            parts.append("[sc]anullsink;[mus]anull[bed]")
        bed = "[bed]"
    else:
        parts.append("[sc]anullsink")
    # Pre-normalisation stems go to <out dir>/stems/ so sync_sheet.py can measure
    # whether each SFX is audible over everything else (constant loudnorm gain cancels).
    rest = ["[voice]"] + ([bed] if bed else [])
    parts.append("".join(rest) + f"amix=inputs={len(rest)}:duration=first:normalize=0,asplit=2[rest][rest_stem]")
    if sfx_labels:
        parts.append("".join(sfx_labels) + f"amix=inputs={len(sfx_labels)}:normalize=0,asplit=2[sfxall][sfx_stem]")
        parts.append("[rest][sfxall]amix=inputs=2:duration=first:normalize=0[out]")
    else:
        parts.append("[rest]anull[out]")
    stem_dir = os.path.join(os.path.dirname(os.path.abspath(out)), "stems")
    os.makedirs(stem_dir, exist_ok=True)
    mixdown = os.path.join(tempfile.mkdtemp(), "mixdown.wav")
    maps = ["-map", "[out]", "-c:a", "pcm_s24le", mixdown,
            "-map", "[rest_stem]", "-c:a", "pcm_s16le", os.path.join(stem_dir, "rest.wav")]
    if sfx_labels:
        maps += ["-map", "[sfx_stem]", "-c:a", "pcm_s16le", os.path.join(stem_dir, "sfx.wav")]
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(parts), *maps],
                   check=True)

    # Loudness: apply gain + a peak limiter (ceiling -2 dBFS after gain), measure the
    # result, correct the gain, repeat. Limiting a peaky mix lowers its loudness, so a
    # single computed gain (or a linear loudnorm, which gives up gain near the
    # true-peak ceiling) lands short of -14 LUFS.
    def measure(path, af=None):
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
        cmd += ["-af", (af + "," if af else "") + "ebur128=peak=true"]
        log = subprocess.run(cmd + ["-f", "null", "-"], capture_output=True, text=True).stderr
        return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])

    gain = -14.0 - measure(mixdown)
    for _ in range(3):
        ceiling = 10 ** ((-2.0 - gain) / 20)
        norm = (f"alimiter=limit={min(1.0, ceiling):.4f}:attack=2:release=50:level=disabled:asc=1,"
                f"volume={gain:.2f}dB")
        err = -14.0 - measure(mixdown, norm)
        if abs(err) < 0.3:
            break
        gain += err
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", "-i", picture, "-i", mixdown,
                    "-af", norm, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-shortest", out], check=True)
    print(f"mixed {len(music_labels)} music beds, {len(sfx_labels)} sfx -> {out}")


if __name__ == "__main__":
    main()
