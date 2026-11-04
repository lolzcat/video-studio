#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""Background-locked stabilization for a shaky webcam / handheld talking head.

Usage: stabilize.py <in.mp4> <out.mp4> --lock-x x0,x1,y0,y1 [--lock-y x0,x1,y0,y1] [--zoom 1.0]
       stabilize.py <in.mp4> <out.mp4> [--person x0,y0,x1,y1] [--radius 30] [--zoom 1.04]
                    [--ss SECONDS] [--t SECONDS]

EDGE LOCK (use this on plain/bright backgrounds): give a strip containing one rigid, high-contrast
edge (a window frame, door, shelf). --lock-x strip holds a VERTICAL edge and fixes side-to-side
shake; --lock-y strip holds a HORIZONTAL edge and fixes up-down. Each frame's averaged profile is
matched to the first frame's (sub-pixel) and the frame is shifted back. Robust where feature
tracking only finds compression noise. (9FE Aaron: window-frame edge jittered 0.25px median,
2px 95th, side to side — measured this way; feature tracking reported noise and made it worse.)

FEATURE MODE (textured backgrounds):
Tracks feature points on the BACKGROUND only (the speaker's rectangle, as fractions of the frame,
is masked out — default 0.33,0.18,0.97,1.0 for a person centred-right in their half), estimates
the camera's frame-to-frame motion (translation + rotation), smooths the camera path with a
moving average of ±radius frames (keeps slow drift, removes shake), warps each frame onto the
smoothed path, and zooms `--zoom` to hide the edges. Audio is copied from the input.

Measure first: if fewer than ~10% of frames move > 0.5px, the camera is steady and this only costs
sharpness. (9FE Aaron Darr: 47% of frames, 95th pct 2.7px/frame — vs 5% for the host's camera.)
"""
import subprocess, sys, cv2, numpy as np


def arg(name, default, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def motion(cap, mask, n):
    ok, prev = cap.read()
    g0 = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    out = []
    for _ in range(n - 1):
        ok, fr = cap.read()
        if not ok:
            break
        g1 = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        p0 = cv2.goodFeaturesToTrack(g0, 300, 0.01, 8, mask=mask)
        dx = dy = da = 0.0
        if p0 is not None and len(p0) >= 8:
            p1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, p0, None, winSize=(21, 21), maxLevel=3)
            a, b = p0[st == 1], p1[st == 1]
            if len(a) >= 6:
                m, _ = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=1.0)
                if m is not None:
                    dx, dy, da = m[0, 2], m[1, 2], float(np.arctan2(m[1, 0], m[0, 0]))
        out.append((dx, dy, da))
        g0 = g1
    return np.array(out)


def profile_shift(ref, cur, up=20, lim=10):
    ref, cur = ref - ref.mean(), cur - cur.mean()
    n = len(ref); xf = np.linspace(0, n - 1, n * up)
    R, C = np.interp(xf, np.arange(n), ref), np.interp(xf, np.arange(n), cur)
    best, bs = 0, -1e18
    for s_ in range(-lim * up, lim * up + 1):
        a = R[max(0, s_):len(R) + min(0, s_)]; b = C[max(0, -s_):len(C) + min(0, -s_)]
        v = float(np.dot(a, b)) / len(a)
        if v > bs: bs, best = v, s_
    return -best / up


def edge_lock(work, dst, sx, sy, zoom):
    cap = cv2.VideoCapture(work)
    n, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames_dx, frames_dy, rv, rh = [], [], None, None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float64)
        dx = dy = 0.0
        if sx:
            pv = g[sx[2]:sx[3], sx[0]:sx[1]].mean(axis=0)
            rv = pv if rv is None else rv
            dx = profile_shift(rv, pv)
        if sy:
            ph = g[sy[2]:sy[3], sy[0]:sy[1]].mean(axis=1)
            rh = ph if rh is None else rh
            dy = profile_shift(rh, ph)
        frames_dx.append(dx); frames_dy.append(dy)
    cap.release()
    X, Y = np.array(frames_dx), np.array(frames_dy)
    # a whole-scene move (camera repositioned, edge occluded) shows as a jump >> jitter: follow it
    print(f"edge lock: side-to-side f2f median {np.median(np.abs(np.diff(X))):.3f}px, range {np.ptp(X):.2f}px; "
          f"up-down range {np.ptp(Y):.2f}px")
    cap = cv2.VideoCapture(work)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                            "-r", str(fps), "-i", "-", "-i", work, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                            "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst],
                           stdin=subprocess.PIPE)
    for i in range(len(X)):
        ok, fr = cap.read()
        if not ok:
            break
        m = np.array([[zoom, 0, (1 - zoom) * w / 2 - X[i] * zoom], [0, zoom, (1 - zoom) * h / 2 - Y[i] * zoom]])
        enc.stdin.write(cv2.warpAffine(fr, m, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT).tobytes())
    enc.stdin.close(); enc.wait(); cap.release()
    print(f"edge-locked {len(X)} frames -> {dst}")


def smooth(path, r):
    k = np.ones(2 * r + 1) / (2 * r + 1)
    pad = np.pad(path, ((r, r), (0, 0)), mode="edge")
    return np.stack([np.convolve(pad[:, i], k, mode="valid") for i in range(path.shape[1])], axis=1)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    x0, y0, x1, y1 = [float(v) for v in arg("--person", "0.33,0.18,0.97,1.0").split(",")]
    radius, zoom = arg("--radius", 30, int), arg("--zoom", 1.04, float)
    ss, t = arg("--ss", None), arg("--t", None)
    work = src
    if ss or t:  # cut the window first so frame indexes match
        work = dst + ".window.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *(["-ss", ss] if ss else []), "-i", src,
                        *(["-t", t] if t else []), "-c:v", "libx264", "-crf", "10", "-preset", "veryfast",
                        "-c:a", "aac", "-b:a", "256k", work], check=True)
    lx, ly = arg("--lock-x", None), arg("--lock-y", None)
    if lx or ly:
        edge_lock(work, dst, [int(v) for v in lx.split(",")] if lx else None,
                  [int(v) for v in ly.split(",")] if ly else None, arg("--zoom", 1.0, float))
        if work != src:
            import os
            os.remove(work)
        return
    cap = cv2.VideoCapture(work)
    n, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    mask = np.full((h, w), 255, np.uint8)
    cv2.rectangle(mask, (int(w * x0), int(h * y0)), (int(w * x1), int(h * y1)), 0, -1)
    d = motion(cap, mask, n)
    cap.release()
    # camera path P[i] = where the background sits in frame i (P[0] = 0); Q = smoothed path.
    # Shifting frame i by Q[i] - P[i] puts the background on the smooth path.
    P = np.vstack([np.zeros((1, 3)), np.cumsum(d, axis=0)])
    corr = smooth(P, radius) - P
    mag = np.hypot(d[:, 0], d[:, 1])
    print(f"camera motion: {100 * (mag > 0.5).mean():.0f}% of frames > 0.5px, 95th {np.percentile(mag, 95):.2f}px/frame")

    cap = cv2.VideoCapture(work)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                            "-r", str(fps), "-i", "-", "-i", work, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                            "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst],
                           stdin=subprocess.PIPE)
    S = cv2.getRotationMatrix2D((w / 2, h / 2), 0, zoom)   # edge-hiding zoom
    for i in range(n):
        ok, fr = cap.read()
        if not ok:
            break
        dx, dy, da = corr[min(i, len(corr) - 1)]
        c, sn = np.cos(da), np.sin(da)
        cx, cy = w / 2, h / 2   # rotate about the centre, then translate
        m = np.array([[c, -sn, cx - c * cx + sn * cy + dx], [sn, c, cy - sn * cx - c * cy + dy]])
        m = np.vstack([S, [0, 0, 1]])[:2] @ np.vstack([m, [0, 0, 1]])
        out = cv2.warpAffine(fr, m, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        enc.stdin.write(out.tobytes())
    enc.stdin.close(); enc.wait(); cap.release()
    if work != src:
        import os
        os.remove(work)
    print(f"stabilized {n} frames -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main()
