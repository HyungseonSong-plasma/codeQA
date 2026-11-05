<div align="center">
<h1>QA Result Conformance Fixtures</h1>
<p><strong>Positive and adversarial tests for source-grounded exchange contracts.</strong></p>
<p>Explicit in-memory snapshots · Fail-closed checks · No fabricated ground truth</p>
</div>

---

## Fixture strategy
The executable cases live in
[`tests/test_qa_result_contract.py`](../../tests/test_qa_result_contract.py).
They produce actual CCG and Mechanical v0.1 data from small, explicit
in-memory source snapshots, then mutate **one contract field at a time** to
exercise failure behavior.

This directory is an explanation of that test strategy; it does **not**
contain fabricated extracted facts presented as ground truth.

## Regression coverage
| Class | Adversarial examples |
| :-- | :-- |
| **Evidence & source** | Missing provenance, uncovered source, unsafe locations |
| **Quality semantics** | Contradictory verdicts, unobserved P1–P8 principles |
| **Measurement & policy** | Changed metric, unit or profile; rule-version drift |
| **Determinism & deltas** | NaN rejection, deterministic serialization, comparable deltas |

The [QA contract catalog](../../contracts/qa/README.md) defines the
versioned report shapes. Passing these scoped tests does not certify
unsupported principles or a universal code-quality PASS.
