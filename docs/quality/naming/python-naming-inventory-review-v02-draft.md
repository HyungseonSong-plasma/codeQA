# Python naming review candidates v0.2 draft (#69)

This is an **independently pinned, unapproved** source inventory for an
independent reviewer. It is *not* the required human-reviewed expected inventory
and does not close #69. No frozen Naming v0.1, CCG, Mechanical or QA Result/Delta
contract is changed.

The source is `src/codeqa/core/naming_glossary.py` at immutable codeQA
revision `dfd94bb25d52642bb2e46766b1ebe074c2f82803`, with declared
Git Blob and SHA-256. Twenty-six candidate declarations/import bindings,
annotated dataclass fields and decorators are recorded with lexical line
witnesses in `fixtures/naming-governance/`. The tests verify exact Git
content identity and source-line presence using the read-only GitReader.

The inventory deliberately preserves `adjudication: null` and
`false_positive_adjudication: null` /
`false_negative_adjudication: null`. A declaration's lexical occurrence
is not evidence of public API intent, runtime override, semantics or safe
rename. For example, a local `tokens` binding must not be silently
promoted to a module-level constant. The candidate fixture is also not a
complete cross-file or repository inventory.

## Required acceptance remaining

An independent human reviewer must adjudicate expected symbols and
false-positive/false-negative examples, with traceable explanations.
Additional #69 work must cover the full policy precedence/exception hierarchy,
imports and aliases, instance and nested declarations, Unicode/confusables,
public/generated/vendor exclusions and fail-closed policy drift. Tests
and a passing CI alone do not satisfy those conditions.
