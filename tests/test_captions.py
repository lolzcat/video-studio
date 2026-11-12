import re, tempfile, unittest

from helpers import captions, load, words

WEAK = load("captions").WEAK
flat = lambda caps: [w["t"] for c in caps for w in c["words"]]
bare = lambda t: re.sub(r"[^\w']", "", t).lower()

LINE = ("The problem with these lists is that they are really old. So we built a tool that finds "
        "the owner of a roofing company in seconds, and it costs nothing to try today.")


class Captions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def check_timeline(self, caps):
        for c in caps:
            self.assertLess(c["in"], c["out"], c)
            self.assertGreaterEqual(c["out"] - c["in"], 0.29, f"flashes by: {c}")
        for a, b in zip(caps, caps[1:]):
            self.assertLessEqual(a["out"], b["in"] + 1e-6, f"two captions on screen: {a} / {b}")

    def test_every_word_shown_once_in_order(self):
        ws = words(LINE)
        caps, _, srt = captions(self.d, ws)
        self.assertEqual([bare(t) for t in flat(caps)], [bare(w["text"]) for w in ws])
        self.check_timeline(caps)
        self.assertEqual(len(re.findall(r"-->", srt)), len(caps))

    def test_default_groups_are_short_and_break_at_sentences(self):
        caps, style, _ = captions(self.d, words(LINE))
        self.assertEqual(style, "default")
        for c in caps:
            self.assertLessEqual(len(c["words"]), 7, c)          # max_words 4, merge up to 7
        for c in caps:                                             # a full stop always ends its group
            for w in c["words"][:-1]:
                self.assertNotRegex(w["t"], r"[.?!]$", c)
        firsts = [c["words"][0]["t"] for c in caps]
        self.assertIn("So", firsts)                                # new sentence starts a new caption

    def test_pause_starts_a_new_caption(self):
        caps, _, _ = captions(self.d, words("one two three four", pauses={2: 0.8}))
        self.assertEqual([[w["t"] for w in c["words"]] for c in caps], [["One", "two"], ["three", "four"]])

    def test_filler_dropped_fixes_and_numbers(self):
        ws = words("um we emailed 1100 revers with Reune today")
        caps, _, _ = captions(self.d, ws, {"fixes": {"revers": "roofers", "Reune": "Reoon"}, "emphasis": ["Reoon"]})
        shown = flat(caps)
        self.assertNotIn("um", [bare(t) for t in shown])
        self.assertIn("1,100", shown)
        self.assertIn("roofers", shown)
        em = {w["t"]: w["em"] for c in caps for w in c["words"]}
        self.assertTrue(em["1,100"] and em["Reoon"])               # numbers + emphasis words get the accent
        self.assertFalse(em["roofers"])
        self.assertEqual(shown[0], "We")                           # first shown word opens the sentence

    def test_plain_has_no_accent_words(self):
        caps, _, _ = captions(self.d, words("we made 500 dollars"), {"plain": True, "emphasis": ["dollars"]})
        self.assertFalse(any(w["em"] for c in caps for w in c["words"]))

    def test_phrase_fix_replaces_a_run(self):
        caps, _, _ = captions(self.d, words("they make times our money back"),
                              {"phrase_fixes": {"times our money": "tons of money"}})
        self.assertEqual(" ".join(flat(caps)).lower(), "they make tons of money back")

    def test_one_line_limit(self):
        caps, _, _ = captions(self.d, words(LINE), {"max_chars": 22, "max_merge": 4})
        for c in caps:
            self.assertLessEqual(len(" ".join(w["t"] for w in c["words"])), 22, c)

    def test_bold_groups_and_word_times(self):
        ws = words(LINE)
        caps, style, _ = captions(self.d, ws, {"style": "bold"})
        self.assertEqual(style, "bold")
        self.assertEqual([bare(t) for t in flat(caps)], [bare(w["text"]) for w in ws])
        self.check_timeline(caps)
        starts = [w["start"] for w in ws]
        self.assertEqual([w["s"] for c in caps for w in c["words"]], starts)   # each word pops on its own time
        for i, c in enumerate(caps):
            text = " ".join(w["t"] for w in c["words"])
            self.assertLessEqual(len(text), 16 + 6, c)             # max_chars 16 (+6 when small words lean in)
            for w in c["words"]:
                self.assertGreaterEqual(w["s"], c["in"] - 1e-6)
            last = c["words"][-1]["t"]
            if i + 1 < len(caps) and not re.search(r"[.?!,]$", last):
                self.assertFalse(all(bare(w["t"]) in WEAK for w in c["words"]),
                                 f"small words stranded alone: {text!r}")

    def test_bold_small_words_lean_on_the_next_group(self):         # 9FE: "of a" / "presentation"
        caps, _, _ = captions(self.d, words("AI can basically build the middle of a presentation for you"),
                              {"style": "bold"})
        groups = [" ".join(w["t"] for w in c["words"]).lower() for c in caps]
        self.assertNotIn("of a", groups)
        self.assertTrue(any(g.startswith("of a presentation") for g in groups), groups)


if __name__ == "__main__":
    unittest.main()
