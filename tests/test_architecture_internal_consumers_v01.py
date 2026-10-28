"""#184: exact-snapshot known importer evidence, not API compatibility proof."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from codeqa.core.dependency import StaticDependency
from codeqa.evaluation.architecture.internal_consumers import (
    InternalConsumerEvidenceError,
    census_internal_consumers,
    render_internal_consumers_markdown,
)
from codeqa.evaluation.architecture.opportunities import (
    discover_architecture_opportunities,
)
from codeqa.evaluation.architecture.policy_triage import (
    triage_cross_role_concentration,
)
from test_architecture_opportunities_v01 import SOURCES, make_report
from test_architecture_policy_triage_v01 import CONCENTRATED, reports


def with_test_importer():
    test_path = "tests/test_view.py"
    sources = {
        **SOURCES,
        test_path: "from orchard.sky.view import view\n",
    }
    test_edge = StaticDependency(
        test_path, "src/orchard/sky/view.py", 1,
        "from orchard.sky.view import view", "top_level",
    )
    inventory, metrics = make_report(
        sources=sources, edges=(*CONCENTRATED, test_edge),
    )
    opportunities = discover_architecture_opportunities(inventory, metrics)
    triage = triage_cross_role_concentration(
        inventory, metrics, opportunities,
        reports()[3],
    )
    return inventory, metrics, triage


class InternalConsumerCensusTests(unittest.TestCase):
    def test_test_path_importer_is_observed_not_certified(self):
        census = census_internal_consumers(*with_test_importer())
        self.assertEqual(census["concentration_source_modules"], 2)
        view = next(m for m in census["modules"]
                    if m["module_path"] == "src/orchard/sky/view.py")
        self.assertEqual(view["known_test_path_importer_pairs"], 1)
        importer = next(i for i in view["importers"]
                        if i["importer_path"] == "tests/test_view.py")
        self.assertEqual(importer["importer_category"], "TEST_PATH_HEURISTIC")
        self.assertEqual(importer["source_witnesses"][0]["line"], 1)
        self.assertEqual(
            importer["source_witnesses"][0]["source_sha256"],
            sha256(b"from orchard.sky.view import view\n").hexdigest(),
        )
        self.assertEqual(census["external_consumers"], "NOT_EVALUATED")
        self.assertEqual(census["semantic_ownership"], "NOT_EVALUATED")
        self.assertEqual(census["decision"], "NOT_EVALUATED")
        human = render_internal_consumers_markdown(census)
        self.assertIn("tests/test_view.py:1", human)
        self.assertIn("not test coverage", human)
        self.assertIn("No observed importer is not proof", human)

    def test_no_signals_has_no_seeded_targets_or_pass(self):
        inv, metrics, opportunities, policy = reports(edges=())
        triage = triage_cross_role_concentration(
            inv, metrics, opportunities, policy,
        )
        census = census_internal_consumers(inv, metrics, triage)
        self.assertEqual(census["modules"], [])
        self.assertEqual(census["known_static_importer_pairs"], 0)
        self.assertEqual(census["decision"], "NOT_EVALUATED")
        self.assertEqual(census, census_internal_consumers(inv, metrics, triage))

    def test_stale_or_forged_witness_fails_closed(self):
        inv, metrics, triage = with_test_importer()
        tampered = deepcopy(metrics)
        test_pair = next(p for p in tampered["resolved_pairs"]
                         if p["source_path"] == "tests/test_view.py")
        test_pair["witnesses"][0]["source_sha256"] = "0" * 64
        tampered["metrics_id"] = sha256(json.dumps({
            k: v for k, v in tampered.items() if k != "metrics_id"
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaises(InternalConsumerEvidenceError):
            census_internal_consumers(inv, tampered, triage)
        stale = deepcopy(triage)
        stale["source_identity"]["snapshot_sha"] = "f" * 40
        with self.assertRaises(InternalConsumerEvidenceError):
            census_internal_consumers(inv, metrics, stale)

    def test_renderer_rejects_modified_consumer_count(self):
        census = census_internal_consumers(*with_test_importer())
        modified = deepcopy(census)
        modified["known_test_path_importer_pairs"] = 0
        with self.assertRaises(InternalConsumerEvidenceError):
            render_internal_consumers_markdown(modified)


if __name__ == "__main__":
    unittest.main()
