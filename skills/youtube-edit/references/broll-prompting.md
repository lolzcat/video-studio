# B-roll: routing, prompting, approval

How `/youtube-edit` decides what each line needs, writes prompts for generated B-roll, and
gets Andrew's OK before anything costs money. Tool: `scripts/broll.py` (review → approve → queue
→ fetch → place). Rules referenced: STYLE.md G6 (real first; generated only for metaphors),
A1 (never stronger than said), S7.

Adapted from two MIT-licensed projects (ideas rewritten for this pipeline, no text copied):
[guangjun5952/minimax-h3-broll-generator](https://github.com/guangjun5952/minimax-h3-broll-generator)
(routing, one-idea shots, audio contract, approval gate) and
[zhouwei713/seedance-prompt](https://github.com/zhouwei713/seedance-prompt) (the "who filmed
this" realism pass).

## 1. Route every line

Read `words_cut.json` as sentences. Give each one exactly one route. **Most lines get no B-roll.**
A visual earns its place only when it adds information, makes a process clear, proves a claim,
sets context, or resets pacing after ~4s of the same shot.

| route | when | made with |
|---|---|---|
| `A_ROLL` | opinion, emotional turn, hedge, direct address, anything whose credibility is the speaker ("I think it explodes") | stay on the face |
| `REAL` | a product, page, post, paper, chart, logo, number, quote: anything factual | browser screenshot / screen recording (G6) |
| `EXISTING` | a real person, place, product the client already has footage of | their library |
| `GRAPHIC` | an exact number, a list, a short statement that must be spelled right | HyperFrames: stat cutaway, band title, chips |
| `GENERATED` | a metaphor, atmosphere, environment, physical action that no real footage shows | Oxen / Higgsfield (this file) |

Never generate what should be `REAL`: no fake UI, logos, results, people, places, documents or
data. If a hypothetical is generated, show the setup, never the outcome he only guessed at (9FE:
the JET A nozzle at the diesel tank is fine; a fireball or a stalled engine is not).

## 2. Write one prompt per shot

One continuous shot per clip, no montage, one idea. In this order, as one paragraph:

1. **Contract**: "One continuous 5-second vertical 3:4 photoreal shot." (generate 3:4 for the
   1080×1500 speaker region; 9:16 for full-frame).
2. **Subject**: what, its material/shape/condition. No faces unless the client supplied the person.
3. **Action**: one main action, at most one secondary change.
4. **Place**: where, what is around it, time of day.
5. **Composition + depth**: shot size, subject position, foreground/mid/background; leave the
   top third calm if a caption or card will sit there.
6. **Camera**: ONE path with a speed word, then settle ("very slow push-in, then holds").
   Max three compatible moves; never pan + zoom + rotate together.
7. **Light, colour, material**: one theme per project, matched to the client's brand
   (9FE: low-key, deep blacks, warm gold highlights).
8. **Time**: 3–4 phases, e.g. "0–1s hand enters; 1–3s nozzle reaches the tank; 3–5s holds".
9. **Realism pass** (step 3): source, device, era, one or two flaws.
10. **Avoid**: no readable text (unless whitelisted below), no logos, watermarks, subtitles, UI,
    faces, flicker, warping hands, extra limbs, jump cuts.
11. **Audio contract**: "Only quiet ambience and the sound of <action>. No music, melody, beat,
    singing, speech, dialogue or voice-over." We mix our own bed and SFX; mute generated audio
    on import anyway.

**Text in frame:** avoid it. If a word is the point (a "JET A" nozzle label), whitelist it exactly
(≤ 12 characters, one group) and check the render; a misspelling is a failed shot. Anything longer
or exact goes to `GRAPHIC`.

Keep prompts under ~1,500 characters. Speed words change rhythm: "very slow", "steady",
"sweeping", "sudden".

## 3. The realism pass (why most AI B-roll looks like AI)

Before writing, decide where this footage would really come from, then write its flaws in:

- **Source**: who filmed it and why ("a truck-stop worker's phone", "a news B-camera", "a drone
  operator scouting the canyon").
- **Device**: phone vertical / handheld DSLR / drone / security cam / 16mm.
- **Era and place details**: what dates it and grounds it (wet asphalt, sodium lights, worn paint).
- **Flaws** (one or two, never all): slight handheld bob, exposure hunting when light changes,
  mild over-sharpening, focus breathing, a lens flare, motion blur on fast movement.
- **Target**: "should read as real footage someone shot, not an ad".

For premium brands (9FE) keep the flaws subtle ("cinema camera on a slider, gentle focus breathing").
For founder/UGC content go further ("phone vertical, slight bob, auto-exposure shifts").

## 4. Plan, review, approve, generate

`<workdir>/broll-plan.json` (one per clip):
```json
{"provider_default": "oxen",
 "shots": [{"id": "B1", "line": "if you put jet fuel in a diesel engine", "start": 6.4, "end": 8.4,
   "route": "GENERATED", "why": "metaphor setup; no real footage of this exists",
   "realism": "cinema camera on a slider at a truck stop at dusk, subtle focus breathing",
   "prompt": "One continuous 5-second vertical 3:4 photoreal shot…",
   "provider": "oxen", "model": "minimax-h3-max-text-to-video", "seconds": 5,
   "resolution": "768P", "aspect_ratio": "3:4", "use_from": 1.2, "approval": "pending"}]}
```
Non-generated routes need only `id`, `line`, `start`, `end`, `route`, `why`.

```bash
python3 "$SK/scripts/broll.py" review  <workdir>             # writes broll-review.md + total cost
python3 "$SK/scripts/broll.py" approve <workdir> --shots B1,B3 --confirm   # only after Andrew's yes
python3 "$SK/scripts/broll.py" queue   <workdir>             # dry run: prints exact payloads
python3 "$SK/scripts/broll.py" queue   <workdir> --go        # submits approved Oxen shots, once each
python3 "$SK/scripts/broll.py" fetch   <workdir>             # downloads finished shots into broll/
python3 "$SK/scripts/broll.py" place   <workdir>             # adds them to overlays.json "broll"
```
- **Ask Andrew** with the review table (shot, line, route, model, seconds, cost, total) and wait
  for a yes naming the shots. "Looks good" about the plan is not approval to generate.
- Changing a prompt after approval resets that shot to `pending`.
- `queue --go` never retries an uncertain submit (it may have been billed); check `fetch` first.
- **Higgsfield shots** (`"provider": "higgsfield"`): pick the model with `models_explore`
  `action: "recommend"` (short query), quote the credit cost from the generation setup, and after
  approval call its `generate_video` tool yourself; record the job id and file in the plan.
- After fetching: look at every shot (contact sheet) for warped hands, garbled text, flicker,
  wrong subject (9FE's "diesel" came back a petrol V8). A failed shot is re-planned, not re-rolled
  blindly; ask before paying for the retry.
