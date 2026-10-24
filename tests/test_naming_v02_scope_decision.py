"""Decision record must retain original issue provenance and deferred work."""
from __future__ import annotations

from pathlib import Path
import unittest


class BoundedNamingScopeDecisionTests(unittest.TestCase):
    def test_every_original_goal_has_explicit_deferred_owner(self):
        source = (Path(__file__).resolve().parents[1]
                  / "docs/naming-v02-bounded-acceptance.md").read_text()
        for old in range(69, 77):
            with self.subTest(issue=old):
                self.assertIn(f"| #{old} |", source)
                self.assertIn("#" + str(old), source)
        for deferred in range(91, 95):
            self.assertIn("#" + str(deferred), source)

    def test_acceptance_never_claims_sdk_or_human_validation(self):
        source = (Path(__file__).resolve().parents[1]
                  / "docs/naming-v02-bounded-acceptance.md").read_text()
        for phrase in ("NOT_EVALUATED", "AWAITING_HUMAN_REVIEW",
                       "UNVERIFIED_PROPOSAL", "No automated source rename",
                       "original long-horizon goals remain OPEN"):
            self.assertIn(phrase, source)


if __name__ == "__main__":
    unittest.main()
