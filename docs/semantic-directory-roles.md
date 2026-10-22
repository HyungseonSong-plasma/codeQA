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

The previous `evaluation/contextual.py → adapters/python_context.py` edge
was eliminated by moving the immutable `FunctionSyntaxContext` transport
record to `core/function_context.py`. Both the Python Adapter and pure
Evaluation now depend on Core. There are **no remaining transitional
exceptions** in this policy; any new `evaluation → adapters` edge is a
`VIOLATION`. Absence of observed forbidden imports is reported as
`NOT_EVALUATED`, not proof that directory semantics are fully aligned.

No CCG 0.1 schema, Mechanical rule or frozen top-level layout is changed.

## Ontology v0.1 companion

The language-neutral ontology enriches this exact role-policy evaluation
with source-backed relationships and explicit normative versus observed
assurance labels. The existing forbidden role checks stay authoritative;
semantic alignment remains NOT_EVALUATED without verified behavior facts.
See [Semantic Architecture Ontology](semantic-architecture-ontology.md).
