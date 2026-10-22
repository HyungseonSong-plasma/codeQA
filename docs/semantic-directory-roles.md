# Directory role policy v0.1

The approved **root layout policy** remains frozen and independent. This
companion policy declares the six `src/codeqa/` roles in
`profiles/semantic-directory-roles-v0.1.json`, their one-way boundaries
and exact, reasoned transitional exceptions.

`evaluation/semantic_layout.py` is repository-neutral and pure. It consumes
tracked relative paths, exact observed source-to-source static import
correspondence and the caller-supplied policy. It emits `VIOLATION` on
unapproved prohibited edges/missing declared roles, `REVIEW_REQUIRED` for
existing named exceptions, and `NOT_EVALUATED` for unclassified folders.
The overall status is **not** a semantic alignment PASS: module names,
algorithmic responsibility, dynamic imports, reexports and runtime dependency
injection cannot be proven from these inputs. Use the evidence index and
human review for those claims.

Current approved *review item* is `evaluation/contextual.py` importing
`adapters/python_context.py`; it should be retired only after a
language-neutral context contract is verified to preserve legacy findings.
A new `evaluation → adapters` edge remains a violation.

No CCG 0.1 schema, Mechanical rule or frozen top-level layout is changed.
