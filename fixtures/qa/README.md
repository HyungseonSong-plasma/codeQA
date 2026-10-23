# QA Result executable conformance fixtures

Positive and adversarial fixtures are source-grounded in
`tests/test_qa_result_contract.py`. They produce real CCG and Mechanical v0.1
data from explicit small in-memory source snapshots, then mutate one
contract field at a time to prove fail-closed behavior. No unsupported
or fabricated extracted fact is stored as a false "ground truth" document.

Regression covers missing provenance, contradictory verdict, uncovered source,
unsafe location, changed metric/unit/profile, rule-version drift, unobserved
P1–P8 principles, NaN, deterministic serialization and comparable deltas.
