"""Documentation that checks itself.

Prose rots because nothing verifies it. Six months on, the spec says 55
food and the config says 70, and the document is actively lying - worse
than no document, because people trust it.

These tests make the documentation's claims executable. They cannot
judge whether the writing is any good. They can catch it becoming false,
which is the failure that actually happens.

One deliberate exemption: **superseded ADRs are not checked**. A frozen
record describes the world as it was when the decision was made, and
ADR-0004 correctly quotes constants that no longer exist in the config.
Holding a historical document to present-day facts would force exactly
the quiet rewriting that the ADR format exists to prevent.
"""
from __future__ import annotations

import re
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ADR_DIR = ROOT / "docs" / "adr"
SPEC = (ROOT / "SPEC.md").read_text()
ADR_INDEX = (ADR_DIR / "README.md").read_text()

VALID_STATUS = ("accepted", "proposed", "superseded by", "deprecated")


def _adr_files():
    return sorted(p for p in ADR_DIR.glob("*.md") if p.name != "README.md")


def _status_of(text: str) -> str:
    m = re.search(r"\*\*Status:\*\*\s*([^·\n]+)", text)
    return m.group(1).strip() if m else ""


class TestTheRecordIsComplete(unittest.TestCase):
    def test_every_adr_is_in_the_index(self):
        listed = set(re.findall(r"\]\((\d{4}-[a-z0-9-]+\.md)\)", ADR_INDEX))
        on_disk = {p.name for p in _adr_files()}
        self.assertEqual(on_disk - listed, set(), "ADR exists but is not indexed")
        self.assertEqual(listed - on_disk, set(), "index points at a missing ADR")

    def test_numbers_are_unique_and_unbroken(self):
        nums = sorted(int(p.name[:4]) for p in _adr_files())
        self.assertEqual(nums, list(range(1, len(nums) + 1)),
                         f"ADR numbering has a gap or a duplicate: {nums}")

    def test_each_one_has_the_three_sections(self):
        for p in _adr_files():
            text = p.read_text()
            for heading in ("## Context", "## Decision", "## Consequences"):
                self.assertIn(heading, text, f"{p.name} is missing {heading}")

    def test_each_status_is_a_real_one(self):
        for p in _adr_files():
            status = _status_of(p.read_text())
            self.assertTrue(status.startswith(VALID_STATUS),
                            f"{p.name} has status {status!r}")

    def test_supersession_links_resolve_both_ways(self):
        """A dangling supersession is how a decision trail quietly breaks."""
        for p in _adr_files():
            text = p.read_text()
            m = re.search(r"superseded by \[ADR-(\d{4})\]\(([^)]+)\)", text)
            if not m:
                continue
            target = ADR_DIR / m.group(2)
            self.assertTrue(target.exists(), f"{p.name} points at missing {m.group(2)}")
            self.assertIn(f"Supersedes:", target.read_text(),
                          f"{target.name} does not acknowledge superseding {p.name}")


class TestTheClaimsAreStillTrue(unittest.TestCase):
    """The checks that actually catch rot: documented numbers against the
    config they describe."""

    def _living_docs(self):
        """SPEC.md plus the ADRs that are still in force. Superseded ones
        describe the past and are deliberately left out."""
        docs = {"SPEC.md": SPEC}
        for p in _adr_files():
            if not _status_of(p.read_text()).startswith("superseded"):
                docs[p.name] = p.read_text()
        return docs

    def test_quoted_costs_and_caps_match_the_config(self):
        from config import SimConfig
        cfg = SimConfig()
        docs = self._living_docs()
        joined = "\n".join(docs.values())

        # Each entry: a phrase the docs use, and the value it must equal.
        for phrase, actual in (
            ("55 food", cfg.BUILD_NURSERY_COST),
            ("55 food", cfg.BUILD_GARDEN_COST),
        ):
            self.assertIn(phrase, " ".join(joined.split()))
            self.assertEqual(int(actual), 55,
                             f"docs say {phrase!r} but the config says {actual}")

        # Normalised, because prose wraps and a phrase that spans two
        # lines would otherwise fail for no reason worth failing for.
        flat = " ".join(joined.split())
        self.assertIn("eats 20% less", flat)
        self.assertAlmostEqual(cfg.BUILD_GARDEN_UPKEEP_CUT, 0.20,
                               msg="docs say 20% but BUILD_GARDEN_UPKEEP_CUT moved")

        self.assertIn("population cap of 60", flat)
        self.assertEqual(cfg.GROWTH_MAX_POPULATION, 60,
                         "docs say the cap is 60 but the config disagrees")

    def test_the_ceilings_the_adr_predicts_are_the_ones_computed(self):
        """ADR-0005 justifies the garden's 20% by three numbers. If the
        model moves, the justification is no longer a justification."""
        from config import SimConfig
        cfg = SimConfig()
        regen = cfg.FOOD_PER_SOURCE / cfg.FOOD_SOURCE_RESPAWN_SECONDS
        plain = regen * cfg.CAPACITY_ATTRITION_ALLOWANCE / cfg.FOOD_UPKEEP_PER_ANT_PER_SEC
        garden = (regen * cfg.CAPACITY_ATTRITION_ALLOWANCE
                  / (cfg.FOOD_UPKEEP_PER_ANT_PER_SEC * (1 - cfg.BUILD_GARDEN_UPKEEP_CUT)))
        adr = (ADR_DIR / "0005-fungus-garden-replaces-rampart.md").read_text()
        self.assertIn("36.7", adr)
        self.assertAlmostEqual(plain, 36.7, delta=0.1)
        self.assertIn("45.8", adr)
        self.assertAlmostEqual(garden, 45.8, delta=0.1)

    # Browser automation for the audio tests. Optional, guarded by
    # skipUnless, and the reason every run reports two skips. See
    # ADR-0006 for why this is permitted and ADR-0001's wording is not.
    OPTIONAL_TEST_ONLY = {"playwright"}

    def _imports(self, py: pathlib.Path):
        """Top-level module names, via ast rather than a regex.

        The regex version reported `the` as a dependency, having matched
        a docstring line beginning "from the kind of ground a nest sits
        on". Parsing is both shorter and correct."""
        import ast
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield a.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    yield node.module.split(".")[0]

    def test_the_shipped_game_has_no_dependencies(self):
        """The claim a reader is most likely to act on, by cloning and
        running. Scoped to what actually ships: a dependency that only a
        skippable test imports cannot stop anyone playing."""
        import sys
        stdlib = set(sys.stdlib_module_names) | {"__future__"}
        pkg = ROOT / "an_ants_life"
        local = {p.name for p in pkg.iterdir() if p.is_dir()}
        local |= {p.stem for p in pkg.glob("*.py")}

        offenders = set()
        for py in pkg.rglob("*.py"):
            if "tests" in py.parts:
                continue
            for top in self._imports(py):
                if top not in stdlib and top not in local:
                    offenders.add(f"{top} ({py.name})")
        self.assertEqual(offenders, set(),
                         f"the game itself must import nothing third-party: "
                         f"{sorted(offenders)}")

    def test_test_only_dependencies_are_declared_and_skippable(self):
        """A test-only tool is allowed, but it has to be listed here and
        it has to skip rather than fail when absent - otherwise a fresh
        clone cannot run its own suite."""
        import sys
        stdlib = set(sys.stdlib_module_names) | {"__future__"}
        pkg = ROOT / "an_ants_life"
        local = {p.name for p in pkg.iterdir() if p.is_dir()}
        local |= {p.stem for p in pkg.glob("*.py")}

        found = {}
        for py in (pkg / "tests").rglob("*.py"):
            for top in self._imports(py):
                if top not in stdlib and top not in local:
                    found.setdefault(top, set()).add(py.name)

        undeclared = set(found) - self.OPTIONAL_TEST_ONLY
        self.assertEqual(undeclared, set(),
                         f"undeclared test dependency: {sorted(undeclared)}. "
                         f"Add it to OPTIONAL_TEST_ONLY and say why in an ADR, "
                         f"or remove it.")
        for dep, files in found.items():
            for name in files:
                text = (pkg / "tests" / name).read_text()
                self.assertIn("skipUnless", text,
                              f"{name} imports {dep} without a skip guard")

    def test_the_spec_does_not_claim_it_has_been_playtested(self):
        """O1 is the binding open question. If someone marks it answered
        without the rest of the spec moving, that is the rot worth
        catching."""
        self.assertIn("Nobody has played a full session", SPEC)


if __name__ == "__main__":
    unittest.main()
