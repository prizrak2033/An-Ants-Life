"""Audio verification, headless.

There is no sound device in CI, so "it works" has to mean something
measurable: every voice is rendered in an OfflineAudioContext and checked
for level. Three bugs were only ever visible this way - a threat tone
that played continuously at every threat level, a compressor that
attenuated signals far below its threshold and inverted the mix, and a
noise burst that kept 1% of its power through its own filter.

Needs playwright and a Chromium build; skipped entirely without them.
"""
from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
import time
import unittest

from tests.harness import _PKG

CHROMIUM = "/opt/pw-browsers/chromium"

try:
    from playwright.sync_api import sync_playwright
    _HAVE_PW = True
except ImportError:
    _HAVE_PW = False

_HAVE_BROWSER = _HAVE_PW and os.path.exists(CHROMIUM)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(_HAVE_BROWSER, "needs playwright and a Chromium build")
class AudioTestBase(unittest.TestCase):
    """Serves the real page from a throwaway simulation on its own port."""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, "server.py", str(cls.port)],
            cwd=_PKG, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.port), 0.25):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            cls.proc.kill()
            raise RuntimeError("server did not start")

        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch(executable_path=CHROMIUM)
        cls.page = cls.browser.new_page()
        cls.errors = []
        cls.page.on("pageerror", lambda e: cls.errors.append(str(e)))
        cls.page.goto(f"http://127.0.0.1:{cls.port}/", wait_until="load", timeout=30000)
        cls.page.wait_for_timeout(1200)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
            cls._pw.stop()
        finally:
            cls.proc.terminate()
            cls.proc.wait(timeout=10)


class TestEventVoices(AudioTestBase):
    """Every one-shot must sound, must not clip, and must arrive at the
    loudness it asked for - the mix is what makes a strike on the queen
    read as more urgent than a policy tick."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.measured = cls.page.evaluate("""async () => {
            const out = {};
            for (const [kind, spec] of Object.entries(window.AUDIO_EVENTS)) {
                const off = new OfflineAudioContext(
                    1, Math.ceil(44100 * (spec[2] + 0.3)), 44100);
                const a = new ColonyAudio();
                a.ctx = off; a.enabled = true; a._buildAmbience();
                a.master.gain.value = 1.0;
                a._voice(spec[0], spec[1], spec[2], spec[3], 0);
                const d = (await off.startRendering()).getChannelData(0);
                let peak = 0, sum = 0;
                for (let i = 0; i < d.length; i++) {
                    const v = Math.abs(d[i]);
                    if (v > peak) peak = v;
                    sum += d[i] * d[i];
                }
                out[kind] = {peak, rms: Math.sqrt(sum / d.length), want: spec[3]};
            }
            return out;
        }""")

    def test_no_voice_is_silent(self):
        silent = [k for k, m in self.measured.items() if m["rms"] < 1e-4]
        self.assertEqual(silent, [], f"silent voices: {silent}")

    def test_no_voice_clips(self):
        clipping = [k for k, m in self.measured.items() if m["peak"] >= 1.0]
        self.assertEqual(clipping, [], f"clipping voices: {clipping}")

    def test_loudness_follows_the_configured_level(self):
        off = {k: round(m["peak"] / m["want"], 2) for k, m in self.measured.items()
               if not 0.6 <= m["peak"] / m["want"] <= 1.6}
        self.assertEqual(off, {}, f"voices not tracking their level: {off}")

    def test_every_kind_has_a_voice(self):
        self.assertGreaterEqual(len(self.measured), 15)


class TestAmbience(AudioTestBase):
    def test_threat_is_silent_at_rest_and_audible_under_attack(self):
        """An LFO sums into a gain param rather than scaling it, so a
        fixed modulation depth sounded the threat tone continuously at
        every threat level - including none - and buried every event."""
        r = self.page.evaluate("""async () => {
            const measure = async (threat) => {
                const off = new OfflineAudioContext(1, Math.ceil(44100*3), 44100);
                const a = new ColonyAudio();
                a.ctx = off; a.enabled = true; a._buildAmbience();
                a.master.gain.value = 1.0;
                // update() bails unless the context is "running", and an
                // offline context is "suspended" until it renders.
                Object.defineProperty(a, "ready", {value: true});
                a.update({game_over: false,
                          colony: {income_per_sec: 1.0, stress: 0.2, population: 30},
                          enemy_counts: {WARRIOR: Math.round(threat*5), RAIDER: 0, PREDATOR: 0},
                          garrison: {home: 4}});
                a.droneGain.gain.cancelScheduledValues(0);
                a.droneGain.gain.value = 0;      // solo the threat branch
                const d = (await off.startRendering()).getChannelData(0);
                let sum = 0;
                for (let i = 0; i < d.length; i++) sum += d[i]*d[i];
                return Math.sqrt(sum / d.length);
            };
            return {rest: await measure(0), attack: await measure(1)};
        }""")
        self.assertLess(r["rest"], 1e-3, f"threat tone audible at rest (rms {r['rest']})")
        self.assertGreater(r["attack"], 10 * max(r["rest"], 1e-9),
                           "threat tone not audible under attack")

    def test_ceiling_holds_without_flattening_a_single_voice(self):
        r = self.page.evaluate("""async () => {
            const render = async (n) => {
                const off = new OfflineAudioContext(1, 44100, 44100);
                const a = new ColonyAudio();
                a.ctx = off; a.enabled = true; a._buildAmbience();
                a.master.gain.value = 1.0;
                for (let i = 0; i < n; i++) a._voice("thud", 70 + i*11, 0.45, 0.85, 0);
                const d = (await off.startRendering()).getChannelData(0);
                let peak = 0;
                for (let i = 0; i < d.length; i++) peak = Math.max(peak, Math.abs(d[i]));
                return peak;
            };
            return {single: await render(1), stacked: await render(6)};
        }""")
        self.assertLess(r["stacked"], 1.0, "six stacked voices clip")
        self.assertGreater(r["single"], 0.6, "a lone voice is being squashed by the ceiling")


class TestMixComesFromConfig(AudioTestBase):
    def test_page_adopts_the_served_mix(self):
        import urllib.request
        served = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/audio-config"))
        got = self.page.evaluate("() => ({levels: AUDIO_LEVELS, events: AUDIO_EVENTS})")
        for k, v in served["levels"].items():
            self.assertAlmostEqual(got["levels"][k], v, places=9, msg=f"level {k}")
        for k, v in served["events"].items():
            self.assertEqual(list(got["events"][k]), list(v), f"event {k}")

    def test_changing_a_level_changes_the_render(self):
        r = self.page.evaluate("""async () => {
            const render = async () => {
                const off = new OfflineAudioContext(1, Math.ceil(44100*0.8), 44100);
                const a = new ColonyAudio();
                a.ctx = off; a.enabled = true; a._buildAmbience();
                a.master.gain.value = 1.0;
                const [v,f,d,g] = AUDIO_EVENTS["queen_hit"];
                a._voice(v, f, d, g, 0);
                const buf = (await off.startRendering()).getChannelData(0);
                let peak = 0;
                for (let i=0;i<buf.length;i++) peak = Math.max(peak, Math.abs(buf[i]));
                return peak;
            };
            const before = await render();
            const o = AUDIO_EVENTS["queen_hit"].slice();
            applyAudioConfig({events: {queen_hit: [o[0], o[1], o[2], o[3]/2]}});
            const halved = await render();
            // The event table is replaced wholesale, not merged, so
            // putting one entry back would leave the page holding only
            // that entry. Re-fetch the real mix instead.
            const cfg = await (await fetch("/audio-config")).json();
            applyAudioConfig(cfg);
            return {before, halved};
        }""")
        self.assertAlmostEqual(r["halved"] / r["before"], 0.5, delta=0.05,
                               msg="halving a configured level did not halve the render")


class TestChroniclePipeline(AudioTestBase):
    def test_only_new_chronicle_entries_sound(self):
        r = self.page.evaluate("""() => {
            const fired = [];
            const orig = audio.event.bind(audio);
            const wasEnabled = audio.enabled;
            // playNewEvents ignores everything while sound is off, which
            // is the whole point of the toggle.
            audio.enabled = true;
            audio.event = (k) => { fired.push(k); return orig(k); };
            lastHeardT = -1;
            const frame = (e) => ({chronicle: e});
            playNewEvents(frame([{t: 100, kind: "policy_changed"}]));
            const afterFirst = fired.length;
            playNewEvents(frame([{t: 100, kind: "policy_changed"},
                                 {t: 101, kind: "queen_hit"}]));
            const afterNew = fired.slice();
            playNewEvents(frame([{t: 100, kind: "policy_changed"},
                                 {t: 101, kind: "queen_hit"}]));
            const afterRepoll = fired.slice();
            audio.event = orig;
            audio.enabled = wasEnabled;
            return {afterFirst, afterNew, afterRepoll};
        }""")
        self.assertEqual(r["afterFirst"], 0, "first frame replayed history")
        self.assertEqual(r["afterNew"], ["queen_hit"], "wrong events sounded")
        self.assertEqual(r["afterRepoll"], r["afterNew"], "re-polling repeated events")

    def test_no_page_errors(self):
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
