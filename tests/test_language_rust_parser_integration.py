"""Cross-PR #122/#93 parser capability is source-backed but not production."""
import json
from pathlib import Path
import unittest
from codeqa.governance.language_matrix import audit_language_matrix

ROOT = Path(__file__).resolve().parents[1]

class RustParserIntegrationTests(unittest.TestCase):
    def test_real_parser_witness_remains_partial(self):
        audit_language_matrix(ROOT)
        manifest = json.loads((ROOT / "profiles/language-execution-matrix-v0.1.json").read_text())
        rust = next(x for x in manifest["languages"] if x["language"] == "Rust")
        parser = next(x for x in rust["layers"] if x["layer"] == "parser")
        mechanical = next(x for x in rust["layers"] if x["layer"] == "mechanical_p1p3")
        self.assertEqual(parser["status"], "PARTIAL_FIXTURE")
        self.assertEqual(parser["entrypoint"], "codeqa.adapters.rust_parser_evidence:parse_rust_syntax")
        self.assertEqual(parser["workflow"], ".github/workflows/rust-parser-evidence.yml")
        self.assertEqual(mechanical["status"], "NOT_EVALUATED")
        self.assertEqual(parser["source"], "src/codeqa/adapters/rust_parser_evidence.py")

if __name__ == "__main__":
    unittest.main()
