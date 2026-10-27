"""#102 bounded proof-to-artifact binding: hashes are not formal equivalence."""
from copy import deepcopy
import unittest
from hashlib import sha256
from codeqa.evaluation.formal_binding import (
    parse_binding, verify_binding, BindingContractError,
)


def sha(data):
    return sha256(data).hexdigest()


class FormalBindingTests(unittest.TestCase):
    def setUp(self):
        self.spec = b"method proof() ensures true {}"
        self.source = b"generated Python text"
        self.record = {
            "schema_version": "0.1", "mode": "GENERATED_CODE_MATCH",
            "specification": {"role": "specification", "path": "payment/spec.dfy", "sha256": sha(self.spec)},
            "generated": {"role": "generated", "path": "build/engine.py", "sha256": sha(self.source)},
            "deployed": {"role": "deployed", "path": "dist/engine.py", "sha256": sha(self.source)},
            "toolchain_id": "dafny-checked-fixture",
            "toolchain_sha256": "1"*64,
            "build_configuration_sha256": "2"*64,
            "attestation_id": "controlled-fixture-attestation",
            "attested_properties": ["payment.invariant"],
        }

    def decision(self, **changes):
        args = {
            "specification_bytes": self.spec,
            "generated_bytes": self.source,
            "deployed_bytes": self.source,
            "expected_toolchain_sha256": "1"*64,
            "expected_build_configuration_sha256": "2"*64,
            "expected_attestation_id": "controlled-fixture-attestation",
            "required_properties": ("payment.invariant",),
        }
        args.update(changes)
        return verify_binding(parse_binding(self.record), **args)

    def test_exact_artifacts_prove_only_identity(self):
        outcome = self.decision()
        self.assertEqual(outcome.status, "IDENTITY_MATCH")
        self.assertIn("SEMANTIC_PRESERVATION_NOT_ESTABLISHED", outcome.reasons)

    def test_deployed_source_mutation_detected(self):
        result = self.decision(deployed_bytes=b"broken runtime source")
        self.assertEqual(result.status, "BINDING_BROKEN")
        self.assertIn("DEPLOYED_HASH_MISMATCH", result.reasons)

    def test_stale_spec_or_generated_output_rejected(self):
        for key in ("specification_bytes", "generated_bytes"):
            with self.subTest(key=key):
                result = self.decision(**{key:b"changed"})
                self.assertEqual(result.status, "BINDING_BROKEN")

    def test_missing_artifact_and_trusted_provenance_unknown(self):
        self.assertEqual(self.decision(deployed_bytes=None).status,"NOT_EVALUATED")
        self.assertEqual(self.decision(expected_attestation_id=None).status,"NOT_EVALUATED")

    def test_changed_toolchain_or_build_configuration_breaks_binding(self):
        for arg in ("expected_toolchain_sha256","expected_build_configuration_sha256"):
            with self.subTest(arg=arg):
                self.assertEqual(self.decision(**{arg:"9"*64}).status,"BINDING_BROKEN")

    def test_missing_property_not_equivalent_to_proof(self):
        self.assertEqual(self.decision(required_properties=("unknown.property",)).status,"NOT_EVALUATED")

    def test_manual_translation_never_verifies_implementation(self):
        self.record["mode"]="MANUAL_TRANSLATION_UNVERIFIED"
        self.record["generated"]=None
        self.assertEqual(self.decision().status,"NOT_EVALUATED")

    def test_forged_declared_generation_mismatch(self):
        self.record["deployed"]["sha256"]="9"*64
        self.assertEqual(self.decision().status,"BINDING_BROKEN")

    def test_reject_invalid_schema_and_paths(self):
        self.record["specification"]["path"]="../escape.dfy"
        with self.assertRaises(BindingContractError):
            parse_binding(self.record)

    def test_reject_noncanonical_paths_in_every_artifact_role(self):
        paths = (
            "./engine.py", "build//engine.py", "build/./engine.py",
            "build/../engine.py", r"build\engine.py", "build/\x00engine.py",
            "build/\nengine.py", "build/\x7fengine.py",
        )
        for role in ("specification", "generated", "deployed"):
            for path in paths:
                with self.subTest(role=role, path=path):
                    forged = deepcopy(self.record)
                    forged[role]["path"] = path
                    with self.assertRaises(BindingContractError):
                        parse_binding(forged)

    def test_deterministic_canonical_binding(self):
        a=parse_binding(self.record)
        self.assertEqual(a.canonical_json(),parse_binding(dict(reversed(list(self.record.items())))).canonical_json())


if __name__=="__main__":
    unittest.main()
