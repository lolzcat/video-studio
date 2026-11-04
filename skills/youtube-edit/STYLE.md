# Andrew's editing style (living rules)

Starter defaults (v0, 2026-11-03). Every rule here should come from Andrew's feedback
over time — replace these as notes come in. Rule IDs are permanent; retired rules are
deleted, not renumbered. Channel pillars: AI tools, cold outreach, ADHD, making money
online. Tone: direct, energetic, tutorial-friendly — not hype-y.

Rules marked *(candidate)* came from tooling or research, not from Andrew's notes yet —
apply them, and confirm/adjust them with Andrew.

## Hook
- **H1** *(candidate)* Something hits the screen within the first 3s (graphic, zoom change or cut), and the first line gives a reason to keep watching.

## Cutting
- **C1** Keep the last clean take of any repeated line unless an earlier take is clearly better delivered.
- **C2** Remove filler ("um", "uh", "like" used as filler, "so yeah"), false starts and restarts.
- **C3** Max pause between sentences: 0.25s in hooks/shorts, 0.4s in full videos. Keep a longer pause only before a punchline. Don't add a jump cut that saves < 150ms — pauses up to ~0.4s in shorts are left alone (reviewer r2: micro-cuts read as jitter).
- **C4** Never cut mid-word. Pad in 0.08s, out 0.12s.
- **C5** Hook (first ~30s) is the tightest part of the video — every line must earn its place.

## Zooms
- **Z1** On jump cuts, alternate framing 1.0 ↔ 1.12–1.18 punch-in so cuts look intentional.
- **Z2** Bigger punch-in (1.3) for emphasis lines and when Andrew says "zoom".
- **Z3** Punch-in focus on the face (eyes in upper third), never crop the top of the head.

## Graphics
- **G1** At most one graphic on screen at a time; no graphic shorter than 1.2s.
- **G2** Hooks: a visual change every 2–4s (cut, zoom, or graphic). Full videos: every 5–8s.
- **G3** Graphics never cover the face — use the side opposite the face, or lower third.
- **G4** Keyword pops: 1–3 words max, appear on the spoken word, exit cleanly.
- **G5** Logos are shown large (≥ 25% of frame width) with a short pop-in.
- **G6** B-roll must be real (real post, page, paper). Highlight the exact line being discussed.
- **T1** *(candidate)* Smallest text on any graphic ≥ 40px at 1080px wide (~14pt on a phone) — this includes kickers, labels and badges.
- **A1** *(candidate)* Every on-screen claim, stat or product name is checked against its source (the screen recording or the real page) and never says more than Andrew said.

## Captions
- **K1** *(candidate, from the "Six months" reference)* Shorts get burned-in captions on every spoken line: 2–4 words per group (max 7 when merging), ≥ 0.5s on screen, never ending on a weak word ("the", "with"…); white Inter 700 76px with a dark outline, numbers and key words in the accent colour; ASR misspellings fixed (product names, numbers as "1,100"). Band sits over cap/chin/chest, never eyes or mouth; never collides with a card; inside the Reels/TikTok safe area (y 220–1500 on 1920, clear of the right-side buttons). Captions stay on while a card repeats the same words (Andrew, 2026-11-03: keep both).
- **K2** Captions and headline cards never compete (Andrew, 2026-11-04, on the Gigi header-band video: "subtitles clashing with the word emphasis up top"). When a layout has headline text (header band, title card), captions go **low**: chest height, just above the platform's bottom UI (≈ y 1350–1480), never directly under the headline. Captions then stay **plain white, no accent words**; the accent colour belongs to the headline only. Keep both on screen (K1), just apart.

## Look
- **L1** Palette: near-black `#0B0B0F` cards, white `#FFFFFF` text, one accent `#7C5CFF`. Accent only for the key word.
- **L2** Fonts: bold geometric sans for titles (e.g. Inter Tight / Satoshi 800), regular for body. No more than 2 families.
- **L3** Motion: fast in (≤ 250ms, ease-out), quick out (≤ 200ms). No bouncy/elastic easing unless asked.
- **L4** Rounded corners 16–24px, soft shadow; no gradients-for-the-sake-of-it.

## Sound
- **S1** Hook: subtle suspense/tension bed. After the hook: low lo-fi hip-hop / chill beat.
- **S2** Music sits well under voice: start around -24 dB with ducking on; voice always wins.
- **S3** SFX are sparse: soft pop/whoosh on graphic entry, click on UI clicks. Never more than one SFX per 2s.
- **S4** SFX gain around -12 to -16 dB; nothing harsh or cartoonish. If the sync sheet says an SFX is buried under the voice, raise it in 3 dB steps up to -6 dB, or drop it.
- **S6** *(candidate)* Every SFX must be heard within 40ms of its visual, and never BURIED (sync sheet SNR < -6 dB in its band) — raise it per S4 or drop it. "Faint" (-6..0 dB) is allowed only once it's at the S4 ceiling; list those for Andrew's ear.
- **B1** *(candidate)* Graphic entries snap to the music beat when a beat is within ±80ms of the spoken word; never move a graphic further than that off the word.
- **S7** *(candidate, 2026-11-04 gigi-dress-code)* A visual that lands while someone is talking gets a high-register SFX (soft chime/sparkle, `chime-soft-01`), not a pop: pops sit in the voice band and stayed BURIED even at -6 dB. If neither is audible at -6 dB, drop the SFX.
- **S5** Final loudness -14 LUFS integrated, true peak ≤ -1 dBTP.

## Animation library
Reusable cards that have worked. Add an entry when Andrew likes one.
Entries marked *(candidate)* were first used in v1 and are not yet approved by Andrew.
- **Seam pill** *(candidate, 2026-11-03 roofer-leads)* — dark rounded pill on the screen/face seam, optional small uppercase kicker + 104px bold line with the key word in accent. In 0.24s power3.out from y+28 / scale 0.92; out 0.18s. Numbers count up (0.8–0.9s). SFX: soft pop at entry.
- **Tool stack** *(candidate)* — 2–3 stacked rows naming tools, each popping in on its spoken word; recommended one gets accent outline + "Best for price"-style badge. SFX: pop on first and last row only.
- **Header band line** *(candidate, 2026-11-04 gigi-dress-code)* — for landscape footage reframed to 9:16: solid brand band at y 0–420 with a small spaced-caps kicker (40px) and a 6px accent rule along its bottom edge that draws in at 0s. One 104px condensed line at a time rises out of the rule (yPercent 100→0, 0.24s power3.out) on its spoken word and sinks out (0.16s); key word in the accent. Lists become outlined chips that pop in on each word. SFX: whoosh on the first line, chime on the payoff.
- **Real-site B-roll** *(candidate)* — screenshot of the real site covering the screen half, slow push-in to 1.06, pill caption with domain. SFX: soft whoosh.
