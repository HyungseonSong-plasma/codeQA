# Project-declared naming glossary evidence — #65

**Opt-in, source-grounded** lexical terminology review. The repository owns
the canonical vocabulary and the exact aliases it considers nonstandard.
No substring similarity, embedding, LLM synonym inference, inferred domain
unit identity or automatic renaming is performed.

Resources `python_naming_glossary_profile` and
`naming_glossary_report_schema` define a versioned, fingerprinted policy.
For instance, `time_step` (canonical) versus `timestep` (explicit alias)
is a known project style contrast. `timestamp` is *not* implicitly
equivalent. Case/underscore/camel segmentation uses token boundaries;
longer explicitly declared terms win when a shorter term is a prefix.

`evaluate_naming_glossary(naming_evidence, exact_sources,
naming_profile=..., glossary=...)` delegates source SHA and AST
declaration-position validation to the existing naming v0.1 evaluator,
then restricts checks to locally controlled symbols whose explicit
path and symbol kind match the glossary policy. Externally bound
imports, inherited methods, unknown DTO mappings, unsupported syntax,
and profile-excluded paths are not silently recast as local names.
Names that contain no declared glossary term produce
`NOT_EVALUATED` rather than a quality PASS.

Findings are `CANONICAL_TERM_OBSERVED` or
`NON_CANONICAL_TERM_REVIEW`, each with original name, lexical owner,
path, exact source line/column and declared canonical/observed term.
One function's name may legitimately contain several unrelated
canonical vocabulary terms; a match is *not semantic equivalence*,
reference identity, or authorization to rewrite other names.
Source selection and profile hash are explicit.

`tests/test_naming_glossary.py` covers time_step/timestep, node_id/nodeid,
CamelCase syntax, unrelated timestamp, unknown external inherited method,
partial parse, deterministic results, out-of-scope names and duplicate
canonical/alias conflicts. The original Naming/CCG/QA v0.1 contracts are
unchanged.

**Future scope:** language-specific tokenization beyond Python,
semantic domain units, glossary review governance and migration planning.
