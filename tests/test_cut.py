import unittest

from helpers import load

cut = load("cut")


def seg(a, b, **kw):
    return {"src": "a.mp4", "in": a, "out": b, **kw}


class Tighten(unittest.TestCase):
    def tighten(self, segs, sil, max_pause=0.25):
        old = cut.silences
        cut.silences = lambda src: sil
        try:
            return cut.tighten(segs, max_pause)
        finally:
            cut.silences = old

    def test_internal_pause_becomes_a_jump_cut(self):
        out = self.tighten([seg(0, 5)], [(2.0, 3.0)])
        self.assertEqual([(s["in"], s["out"]) for s in out], [(0, 2.125), (2.875, 5)])
        self.assertEqual([s["trim_piece"] for s in out], [False, True])   # 2nd piece is not a real edit
        kept_pause = out[1]["in"] - out[0]["out"]
        self.assertAlmostEqual(1.0 - kept_pause, 0.25, places=3)          # exactly max_pause is left

    def test_small_saving_is_left_alone(self):                            # C3: < 150 ms reads as jitter
        out = self.tighten([seg(0, 5)], [(2.0, 2.35)])
        self.assertEqual([(s["in"], s["out"]) for s in out], [(0, 5)])

    def test_edge_silence_is_trimmed(self):
        out = self.tighten([seg(0, 5)], [(0.0, 0.5), (4.5, 5.0)])
        self.assertEqual([(s["in"], s["out"]) for s in out], [(0.42, 4.62)])

    def test_raw_segment_untouched(self):
        out = self.tighten([seg(0, 5, raw=True)], [(2.0, 3.0)])
        self.assertEqual([(s["in"], s["out"]) for s in out], [(0, 5)])

    def test_never_loses_speech(self):
        sil = [(1.0, 1.6), (2.5, 3.4), (4.0, 4.3)]
        out = self.tighten([seg(0, 6)], sil, 0.25)
        for a, b in zip(out, out[1:]):
            self.assertLess(a["out"], b["in"])
            gap = (a["out"], b["in"])                                     # every removed span is inside a silence
            self.assertTrue(any(sa <= gap[0] and gap[1] <= sb for sa, sb in sil), gap)


class Zooms(unittest.TestCase):
    def test_long_pieces_alternate(self):
        segs = cut.alternate_zooms([seg(0, 3), seg(10, 13), seg(20, 23)], 1.15)
        self.assertEqual([s["zoom"] for s in segs], [1.0, 1.15, 1.0])

    def test_framing_holds_at_least_2_5s(self):                           # Z1: "camera micro shakes"
        segs = cut.alternate_zooms([seg(i * 10, i * 10 + 1) for i in range(8)], 1.15)
        t, last_change, prev = 0.0, 0.0, segs[0]["zoom"]
        for s in segs:
            if s["zoom"] != prev:
                self.assertGreaterEqual(t - last_change, cut.MIN_ZOOM_HOLD - 1e-6)
                last_change, prev = t, s["zoom"]
            t += s["out"] - s["in"]
        self.assertGreater(len({s["zoom"] for s in segs}), 1)             # it does still change

    def test_trimmed_pause_and_sliver_keep_framing(self):
        segs = cut.alternate_zooms([seg(0, 3), seg(3.5, 6.5, trim_piece=True), seg(10, 10.4), seg(20, 23)], 1.15)
        self.assertEqual([s["zoom"] for s in segs], [1.0, 1.0, 1.0, 1.15])

    def test_speed_counts_output_time(self):                              # 3s at 1.25x is 2.4s on screen: too soon
        segs = cut.alternate_zooms([seg(0, 3), seg(10, 13)], 1.15, speed=1.25)
        self.assertEqual([s["zoom"] for s in segs], [1.0, 1.0])

    def test_zoom_lock_wins(self):
        segs = cut.alternate_zooms([seg(0, 1), seg(10, 11, zoom=1.3, zoom_lock=True)], 1.15)
        self.assertEqual(segs[1]["zoom"], 1.3)


class Sources(unittest.TestCase):
    def check(self, sizes):
        old = cut.probe
        cut.probe = lambda src: sizes[src]
        try:
            cut.check_sources(list(sizes), *sizes["a.mp4"])
        finally:
            cut.probe = old

    def test_same_shape_passes(self):
        self.check({"a.mp4": (1920, 1080, 30.0), "b.mp4": (3840, 2160, 30.0)})

    def test_different_shape_stops(self):
        with self.assertRaises(SystemExit) as e:
            self.check({"a.mp4": (1920, 1080, 30.0), "b.mp4": (1080, 1920, 30.0)})
        self.assertIn("stretched", str(e.exception))


if __name__ == "__main__":
    unittest.main()
