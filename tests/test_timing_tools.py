import json, os, shutil, subprocess, tempfile, unittest

from helpers import load, run, words


class Remap(unittest.TestCase):
    def test_cards_follow_their_words_after_a_recut(self):
        old = words("we sent one thousand emails and booked nine calls this week")
        new = [dict(w) for w in old]
        for w in new[5:]:                       # a 1.0s pause was added before "and"
            w["start"], w["end"] = round(w["start"] + 1.0, 3), round(w["end"] + 1.0, 3)
        with tempfile.TemporaryDirectory() as d:
            p = lambda n: os.path.join(d, n)
            json.dump(old, open(p("old.json"), "w")); json.dump(new, open(p("new.json"), "w"))
            ov = {"cards": [{"id": "emails", "start": old[2]["start"], "end": old[4]["end"], "spoken": {"start": 1}},
                            {"id": "calls", "start": old[7]["start"], "end": old[8]["end"],
                             "events": {"nine": old[7]["start"]}},
                            {"id": "scoreboard", "persistent": True, "start": 0, "end": 99}],
                  "broll": [{"file": "x.mp4", "start": old[9]["start"], "end": old[10]["end"]}]}
            json.dump(ov, open(p("ov.json"), "w"))
            r = run("remap.py", p("old.json"), p("new.json"), p("ov.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            got = {c["id"]: c for c in json.load(open(p("ov.json")))["cards"]}
            self.assertAlmostEqual(got["emails"]["start"], old[2]["start"], places=3)       # before the change
            self.assertNotIn("spoken", got["emails"])
            self.assertAlmostEqual(got["calls"]["start"], old[7]["start"] + 1.0, places=3)  # after: moved 1s
            self.assertAlmostEqual(got["calls"]["events"]["nine"], old[7]["start"] + 1.0, places=3)
            self.assertEqual((got["scoreboard"]["start"], got["scoreboard"]["end"]), (0, 99))
            br = json.load(open(p("ov.json")))["broll"][0]
            self.assertAlmostEqual(br["start"], old[9]["start"] + 1.0, places=3)


class Transcribe(unittest.TestCase):
    t = load("transcribe")

    def test_words_stretched_over_a_pause_are_clamped(self):
        ws = [{"text": "leads.", "start": 1.0, "end": 2.4}, {"text": "Now", "start": 2.45, "end": 3.9}]
        out = self.t.clamp_to_silence(ws, [(1.5, 2.4), (2.9, 3.5)])
        self.assertEqual(out[0]["end"], 1.55)   # the word ended where the silence began

    def test_sentences_split_on_stops_and_long_gaps(self):
        ws = words("First line here. Second one", pauses={3: 0.0}) + words("after a gap", start=10)
        self.assertEqual([len(s) for s in self.t.sentences(ws)], [3, 2, 3])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class QC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.clip = os.path.join(cls.tmp.name, "clip.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=2",
                        "-f", "lavfi", "-i", "sine=f=440:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", cls.clip], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_wrong_size_fps_and_duration_fail(self):
        r = run("qc.py", self.clip, "--expect-size", "1080x1920", "--expect-fps", "24", "--expect-duration", "9")
        self.assertEqual(r.returncode, 1)
        for msg in ("FAIL  frame size 320x568, expected 1080x1920", "FAIL  frame rate 30.000 fps, expected 24",
                    "FAIL  duration"):
            self.assertIn(msg, r.stdout)

    def test_right_size_and_fps_are_not_reported(self):
        r = run("qc.py", self.clip, "--expect-size", "320x568", "--expect-fps", "30", "--expect-duration", "2")
        self.assertNotIn("frame size", r.stdout)
        self.assertNotIn("frame rate", r.stdout)
        self.assertNotIn("FAIL  duration", r.stdout)
        self.assertIn("picture: 320x568 @ 30.000 fps", r.stdout)

    def test_off_target_loudness_fails(self):       # a raw sine is nowhere near -14 LUFS
        r = run("qc.py", self.clip)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  integrated loudness", r.stdout)


if __name__ == "__main__":
    unittest.main()
