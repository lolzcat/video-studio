# Feedback log

One line per note: `YYYY-MM-DD | video | raw note | → rule ID (added/changed/removed)`

2026-11-03 | roofer-leads v1→v2 | (tooling, not Andrew's note) plan check: kickers/badge 22–24px unreadable on phone | → T1 added (candidate), labels 40px in v2
2026-11-03 | roofer-leads v1→v2 | (tooling) sync sheet: pop file has 95ms leading silence → pops sounded late; pop at 6.10s buried -10.5 dB under voice | → mix.py trims SFX lead-in; S4 amended; S6 added (candidate)
2026-11-03 | roofer-leads v2 | (Andrew asked for beat snapping) | → B1 added (candidate); 3/12 visuals snapped (±80ms)
2026-11-03 | skill | (Andrew approved: reviewer, rule checks, sync sheet) | → H1, A1 added (candidate); SKILL steps 5–8b updated
2026-11-03 | roofer-leads v2 | reviewer r1 6.0/revise: neighbours shared zoom, all punches 1.08 | → cut.py alternate_zooms + "punch" 1.15 (Z1 enforced)
2026-11-03 | roofer-leads v2 | reviewer r1: punch-in cropped the screen half | → cut.py "zoom_region" (face-only zoom on split recordings)
2026-11-03 | roofer-leads v2 | reviewer r1: "BEST FOR PRICE"/"EVERY CITY" overstate what was said | → wording fixed; A1 applied
2026-11-03 | roofer-leads v2 | reviewer r1: "And just like that" opener, filler "now"s, false outro, trailing ending | → SKILL step 3 editorial checklist + gaps.py + raw tail
2026-11-03 | roofer-leads v2 | reviewer r1: names popped up to 350ms before spoken; loop restart slipped the beat | → words_cut from ASR on the cut; timing.py loops
2026-11-03 | roofer-leads v3 | reviewer r2 6.6/revise BLOCKER: last word clipped ("lead-"), "conta-" — cut inside a consonant closure | → gaps.py flags <=60ms dips as closures; cut after the burst
2026-11-03 | roofer-leads v3 | reviewer r2: 0.5s segments + zoom toggles read as jitter | → cut.py MIN_SAVE 150ms; C3 amended
2026-11-03 | roofer-leads v3 | reviewer r2: reason ("$0 → free tool") came after the result | → reordered; editorial checklist
2026-11-03 | roofer-leads v3 | reviewer r2: "IN ONE CITY" unsaid; "Lousy" stated as fact; kickers at T1 floor; rows see-through | → NEW YORK CITY (on screen), PROBABLY, kickers 44px #C8C8D0, opaque rows
2026-11-03 | roofer-leads v3 | reviewer r2: no tension bed in hook (S1); loop restart under payoff | → tension-hook bed 0–7.2s → lo-fi single pass; timing.py "beats": false for ambient beds
2026-11-03 | roofer-leads v4 | (QC) loudness landed -15.3 — limiter/TP cap ate gain | → mix.py iterative gain+limiter loop (-14.2 LUFS)
2026-11-03 | roofer-leads v4 | reviewer r3 7.1/revise (final round): disputed blocker "If" clipped at 0:28 (my gap map: dip at 5.78 before "if"; reviewer ASR missed "If" 2/3) — needs Andrew's ear | → open
2026-11-03 | roofer-leads v4 | reviewer r3: c5 pop left at -6 dB after re-time, 26.5 dB clear (harsh) | → sync_sheet HOT check; c5 back to -14 (v5)
2026-11-03 | roofer-leads | reviewers disagreed on the ending (r1: end on "leads"; r3: keep "that we can sell to") | → taste call for Andrew
2026-11-03 | six-months reference + roofer v6 | (Andrew: "Yes, add captions") — reference reel captions every line; pipeline had none | → K1 (candidate), captions.py + captions-snippet.html, check_plan K1 collision + Reels/TikTok UI-zone checks
2026-11-03 | roofer v6 | Andrew: "Keep both" — captions stay on even when a card shows the same words | → K1 amended (Andrew-approved detail)
2026-11-04 | gigi-dress-code v4 | Andrew: "Subtitles clashing with the word emphasis up top" — captions at y 530 sat right under the band headline, both with gold emphasis | → K2: captions low (chest, above bottom UI), plain white, accent only in the headline
2026-11-04 | 9fe-aaron-darr jet-fuel v1 | reviewers: G6 says B-roll must be real; Andrew asked for Oxen-generated B-roll | → G6 exception: generated B-roll may illustrate a metaphor, never evidence, never a hedged claim as fact (r1 blocker: fireball on "I think it explodes" after the hedge was cut)
2026-11-04 | 9fe-aaron-darr v4 | Andrew: "the caption at the top distract from the ones at the bottom, i think the ones at the top should be the ones over the actual video with the top being the same text" | → K2 rewritten: band = one static title per clip; emphasis moves to the captions over the video (accent key words); name tag + stats over the video
2026-11-04 | 9fe-aaron-darr v5 | Andrew: "Titles work" (static band titles + caption emphasis) | → Header band title approved (no longer candidate); titles ≤ 30 chars, his words, one accent word
2026-11-04 | 9fe never-lose-money v6 | Andrew: "fix it" on tons/turns — 5 ASR passes all hear "tons" | → K1: caption what the audio supports, never an interpretation; meaning goes in a card. Jet B-roll: stalling V8 replaced by a neutral JET A nozzle shot on "if you put jet fuel in a diesel engine"
2026-11-04 | 9fe clips v7 | Andrew: "whats with the camera micro shakes" — zoom flipped every 1.5–2s (every trimmed pause counted as a jump cut, pieces down to 0.24s) and 1.25× at 24 fps dropped 1 frame in 5 | → Z1: framing changes ≥ 2.5s apart, pause trims/slivers keep framing; cut.py speed keeps every frame (30 fps)
