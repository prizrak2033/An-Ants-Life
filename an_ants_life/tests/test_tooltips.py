"""Every control the player can touch has to explain itself.

The game shipped with three tooltips and seven hint strings written in
the voice of the code - "Recruits nearby idle workers, up to a limit" -
which says what the function does and not what the player should do. The
cost of that showed up in measurement: of the two works, one is a much
better first purchase, and nothing on screen said so, so a player had to
reason out the colony's arithmetic to avoid the worse run.

These tests are about coverage and voice, not wording. They cannot tell
whether a sentence is good. They can tell whether a control is mute, and
whether the copy has drifted back into internals.
"""
from __future__ import annotations

import re
import pathlib
import unittest

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
HTML = (WEB / "index.html").read_text()
JS = (WEB / "app.js").read_text()

# Controls that are their own explanation, or that carry live text.
EXEMPT = {
    "pause-btn", "restart-btn",          # universally understood
    "game-over-restart", "game-over-dismiss",
    "volume-slider",
}


def _tooltip_keys() -> set:
    body = JS[JS.index("const TOOLTIPS = {"):JS.index("function applyTooltips")]
    return set(re.findall(r'"([^"]+)":\s*$|"([a-z:\-\.A-Z]+)":', body, re.M)) or set(
        re.findall(r'^\s*"([^"]+)":', body, re.M))


class TestEveryControlExplainsItself(unittest.TestCase):
    def test_no_control_is_mute(self):
        keys = {k for k in re.findall(r'^\s*"([^"]+)":', JS, re.M)}
        ids = set(re.findall(r'<(?:button|input|select)[^>]*id="([^"]+)"', HTML))
        missing = sorted(i for i in ids - keys - EXEMPT)
        self.assertEqual(missing, [], f"controls with no tooltip: {missing}")

    def test_every_data_driven_control_is_covered(self):
        keys = {k for k in re.findall(r'^\s*"([^"]+)":', JS, re.M)}
        for attr in ("tool", "layer", "work", "speed"):
            for val in set(re.findall(rf'data-{attr}="([^"]+)"', HTML)):
                self.assertIn(f"{attr}:{val}", keys,
                              f"{attr} '{val}' has no tooltip")

    def test_the_table_is_the_only_source(self):
        """Copy in two places drifts apart; that is how the old wording
        survived three rewrites of the works."""
        self.assertNotIn('title="', HTML,
                         "tooltip text belongs in TOOLTIPS, not in markup")


class TestVoice(unittest.TestCase):
    """Not a judge of good writing - a guard against the copy sliding
    back into describing the implementation."""

    INTERNALS = [
        "carrying_capacity", "upkeep", "pheromone", "stigmerg", "config",
        "dt ", "per_sec", "tick", "CI ", "p=", "significant", "paired",
        "BUILD_", "GROWTH_", "cfg.",
    ]

    def _copy(self):
        body = JS[JS.index("const TOOLTIPS = {"):JS.index("function applyTooltips")]
        # Strings only, so the section's own comments are not scanned.
        return " ".join(re.findall(r'"((?:[^"\\]|\\.)*)"', body))

    def test_no_internal_terms_reach_the_player(self):
        copy = self._copy().lower()
        for term in self.INTERNALS:
            self.assertNotIn(term.lower(), copy,
                             f"tooltip copy leaks an internal term: {term!r}")

    def test_no_statistics_reach_the_player(self):
        """The findings behind this copy stay in the README."""
        copy = self._copy()
        self.assertNotRegex(copy, r"\d+\s*/\s*32", "a sample size reached the UI")
        self.assertNotRegex(copy, r"\d+%", "a raw percentage reached the UI")

    def test_the_two_works_say_when_they_are_worth_buying(self):
        """The whole reason for this pass. Both works are affordable
        within minutes and one is the better first buy; if the copy does
        not say so, the player has to derive it."""
        # Scoped to the table: these keys are also referenced elsewhere
        # in the file, and slicing the whole of it picks up the wrong one.
        body = JS[JS.index("const TOOLTIPS = {"):JS.index("function applyTooltips")]
        nursery = body[body.index('"work:nursery"'):body.index('"work:garden"')]
        garden = body[body.index('"work:garden"'):body.index('"rally-btn"')]
        self.assertIn("early", nursery)
        self.assertIn("large", garden)


if __name__ == "__main__":
    unittest.main()


class TestStartingTheGame(unittest.TestCase):
    """The first thing anyone runs, including a friend trying it cold.

    `python3 -m server --port 8731` used to die on int() with a
    traceback, which is a poor greeting.
    """

    def test_every_reasonable_way_of_asking_for_a_port_works(self):
        from server import parse_port, DEFAULT_PORT
        self.assertEqual(parse_port([]), DEFAULT_PORT)
        for argv in (["8731"], ["--port", "8731"], ["-p", "8731"], ["--port=8731"]):
            self.assertEqual(parse_port(argv), 8731, argv)

    def test_a_bad_port_explains_itself_instead_of_crashing(self):
        from server import parse_port
        for argv in (["abc"], ["99999"], ["0"], ["--port"]):
            with self.assertRaises(SystemExit) as caught:
                parse_port(argv)
            self.assertTrue(str(caught.exception).strip(),
                            f"{argv} exited with no explanation")
