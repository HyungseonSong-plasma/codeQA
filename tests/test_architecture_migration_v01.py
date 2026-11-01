"""B5 adversarial static migration evidence; no automatic source rewriting."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from codeqa.core.dependency import DependencyGraph
from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory
from codeqa.evaluation.architecture.metrics import analyze_architecture_metrics
from codeqa.evaluation.architecture.opportunities import discover_architecture_opportunities
from codeqa.evaluation.architecture.scenarios import generate_virtual_layout_scenarios
from codeqa.evaluation.architecture.migration import (
    ArchitectureMigrationError, assess_architecture_migration,
)
from test_architecture_scenarios_v01 import (
    SHA, POLICY, PROFILE, SOURCES, CONCENTRATED,
)


def setup(*, extra=None, missing=(), edges=CONCENTRATED, policy=POLICY):
    sources = {
        **SOURCES,
        "src/orchard/sky/view.py":
            "from orchard.earth.model import Model\nfrom . import other\nclass View: pass\n",
        **(extra or {}),
    }
    provided = {p: v for p, v in sources.items() if p not in missing}
    inventory = analyze_architecture_inventory(SHA, sorted(sources), provided, policy)
    analyzed = tuple(sorted(p for p in provided if p.endswith(".py")))
    graph = DependencyGraph(SHA, analyzed, (), tuple(edges), ())
    metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
    opportunities = discover_architecture_opportunities(inventory, metrics)
    scenarios = generate_virtual_layout_scenarios(inventory, metrics, opportunities, policy)
    return inventory, scenarios, provided


class MigrationImpactTests(unittest.TestCase):
    def test_static_alias_relative_init_export_and_external_unknown(self):
        extra = {
            "src/orchard/earth/consumer.py":
                "import orchard.sky.view as alias\nimport orchard.sky.view\n"
                "from orchard.sky.view import View as Named\n"
                "from orchard.sky import view\n"
                "from orchard.sky import *\n"
                "import importlib\n"
                "x = importlib.import_module('orchard.sky.view')\n"
                "y = importlib.import_module(module_name)\n",
            "src/orchard/sky/__init__.py":
                "from .view import View\n__all__ = ['View']\n",
            "tests/test_consumer.py": "from orchard.sky.view import View\n",
            "pyproject.toml": '[project.scripts]\nrunner = "orchard.sky.view:View"\n',
            "docs/example.md": "Import orchard.sky.view for a demonstration.\n",
        }
        inv, scenarios, sources = setup(extra=extra)
        self.assertEqual(len(scenarios["candidates"]), 1)
        before = deepcopy((inv, scenarios, sources))
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual((inv, scenarios, sources), before)
        self.assertEqual(report, assess_architecture_migration(inv, scenarios, sources))
        impact = report["candidates"][0]
        kinds = {site["kind"] for site in impact["observed_sites"]}
        self.assertTrue({
            "STATIC_IMPORT", "ALIASED_IMPORT", "ALIASED_FROM_IMPORT",
            "STAR_IMPORT",
            "FROM_IMPORT", "RELATIVE_IMPORT", "DYNAMIC_IMPORT_LITERAL",
            "PACKAGING_REFERENCE", "CONFIG_OR_DOC_REFERENCE",
            "TEST_OR_SCRIPT_REFERENCE",
        } <= kinds)
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED", impact["unknowns"])
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertIn("CLI_ENTRYPOINT_REVIEW", impact["unknowns"])
        self.assertIn("STAR_IMPORT_REVIEW", impact["unknowns"])
        self.assertIn("INIT_REEXPORT_REVIEW", impact["unknowns"])
        self.assertIn("src/orchard/sky/__init__.py", impact["initializer_export_paths"])
        self.assertGreater(impact["observed_site_count"], 5)
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")
        self.assertEqual(report["decision"], "NOT_EVALUATED")
        self.assertEqual(report["evidence_status"], "INCOMPLETE")
        self.assertTrue(all(s["rewrite_status"] == "REVIEW_REQUIRED"
                            for s in impact["observed_sites"]))

    def test_aliased_dynamic_imports_are_migration_consumer_witnesses(self):
        # Static evidence must include import helpers brought into scope via
        # from-imports or module aliases, without claiming runtime binding.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/dynamic_client.py": (
                "from importlib import import_module as load\n"
                "import importlib as module_loader\n"
                "from pkgutil import resolve_name as resolve\n"
                "first = load('orchard.sky.view')\n"
                "second = module_loader.import_module('orchard.sky.view')\n"
                "third = resolve('orchard.sky.view:View')\n"
                "fourth = load(dynamic_name)\n"
            ),
            "src/orchard/earth/unrelated.py": (
                "def import_module(name): return name\n"
                "value = import_module('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"]
        self.assertEqual(
            [(site["path"], site["line"], site["expression"]) for site in sites],
            [
                ("src/orchard/earth/dynamic_client.py", 4, "orchard.sky.view"),
                ("src/orchard/earth/dynamic_client.py", 5, "orchard.sky.view"),
                ("src/orchard/earth/dynamic_client.py", 6, "orchard.sky.view:View"),
            ],
        )
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertIn("DYNAMIC_IMPORT_REVIEW", impact["unknowns"])
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED", impact["unknowns"])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_keyword_name_dynamic_import_targets_are_witnessed(self):
        # Python import helpers accept a keyword target. An analyzer that
        # reads only args[0] misses these known consumers during migration.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/keyword_client.py": (
                "import importlib as loader\n"
                "from pkgutil import resolve_name as resolve\n"
                "first = loader.import_module(name='orchard.sky.view')\n"
                "second = resolve(name='orchard.sky.view:View')\n"
                "third = __import__(name='orchard.sky.view')\n"
                "fourth = loader.import_module(name=runtime_target)\n"
                "fifth = loader.import_module(**kwargs)\n"
                "sixth = loader.import_module(name='elsewhere.module')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/keyword_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(3, "orchard.sky.view"), (4, "orchard.sky.view:View"),
             (5, "orchard.sky.view")],
        )
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertIn("DYNAMIC_IMPORT_REVIEW", impact["unknowns"])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_relative_dynamic_imports_require_literal_package_witnesses(self):
        # importlib.import_module resolves leading dots against package=.
        # A literal relative name without a literal valid package must not
        # be reported as a known migration consumer.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/relative_client.py": (
                "import importlib as loader\n"
                "known_keyword = loader.import_module('.view', package='orchard.sky')\n"
                "known_positional = loader.import_module('..sky.view', 'orchard.earth')\n"
                "unknown_package = loader.import_module('.view', package=runtime_package)\n"
                "missing_package = loader.import_module('.view')\n"
                "unrelated = loader.import_module('.model', package='orchard.earth')\n"
                "invalid_depth = loader.import_module('...view', package='orchard.sky')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/relative_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(2, ".view"), (3, "..sky.view")],
        )
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertIn("DYNAMIC_IMPORT_REVIEW", impact["unknowns"])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_builtin_import_relative_level_is_not_absolute_consumer(self):
        # __import__(..., level>0) resolves relative to the calling package,
        # so a dotted literal is not proof of an absolute old-module consumer.
        # Nonliteral levels and unpacked arguments remain unknown.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/builtin_relative_client.py": (
                "known_default = __import__('orchard.sky.view')\\n"
                "known_keyword = __import__(name='orchard.sky.view', level=0)\\n"
                "known_positional = __import__('orchard.sky.view', None, None, (), 0)\\n"
                "relative_keyword = __import__('orchard.sky.view', level=1)\\n"
                "relative_positional = __import__('orchard.sky.view', None, None, (), 1)\\n"
                "unknown_level = __import__('orchard.sky.view', level=runtime_level)\\n"
                "unpacked = __import__('orchard.sky.view', *args)\\n"
                "unrelated = __import__('orchard.earth.model', level=0)\\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/builtin_relative_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(1, "orchard.sky.view"), (2, "orchard.sky.view"),
             (3, "orchard.sky.view")],
        )
        self.assertIn("DYNAMIC_IMPORT_TARGET_UNKNOWN", impact["unknowns"])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_dynamic_helper_aliases_do_not_leak_across_lexical_scopes(self):
        # B5 must not claim a consumer from an alias imported only in
        # another function, or from a shadowed argument/local/builtin.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/scoped_client.py": (
                "from importlib import import_module as load\n"
                "import importlib as loader\n"
                "module_call = load('orchard.sky.view')\n"
                "def local():\n"
                "    from pkgutil import resolve_name as resolve\n"
                "    return resolve('orchard.sky.view:View')\n"
                "def unrelated():\n"
                "    return resolve('orchard.sky.view:View')\n"
                "def shadow(load, loader):\n"
                "    load('orchard.sky.view')\n"
                "    return loader.import_module('orchard.sky.view')\n"
                "def rebind():\n"
                "    load = lambda name: name\n"
                "    return load('orchard.sky.view')\n"
                "def __import__(name): return name\n"
                "bad = __import__('orchard.sky.view')\n"
                "class Holder:\n"
                "    from importlib import import_module as class_load\n"
                "    body = class_load('orchard.sky.view')\n"
                "    def method(self):\n"
                "        return class_load('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/scoped_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(3, "orchard.sky.view"), (6, "orchard.sky.view:View"),
             (19, "orchard.sky.view")],
        )
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")


    def test_comprehension_targets_do_not_shadow_outer_import_helpers(self):
        # Comprehension assignment targets have implicit local scope. A
        # same-named target must not erase genuine module-level consumers.
        # A class-local helper is not visible inside a comprehension body.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/comprehension_client.py": (
                "import importlib as loader\n"
                "from importlib import import_module as load\n"
                "bad_list = [loader.import_module('orchard.sky.view') for loader in (1,)]\n"
                "bad_set = {load('orchard.sky.view') for load in (lambda x: x,)}\n"
                "bad_dict = {loader: loader.import_module('orchard.sky.view') for loader in (1,)}\n"
                "bad_gen = (load('orchard.sky.view') for load in (lambda x: x,))\n"
                "good = loader.import_module('orchard.sky.view')\n"
                "good_alias = load('orchard.sky.view')\n"
                "good_inner = [load('orchard.sky.view') for item in range(1)]\n"
                "class Holder:\n"
                "    import importlib as class_loader\n"
                "    bad_class = [class_loader.import_module('orchard.sky.view') for item in range(1)]\n"
            ),
            "src/orchard/earth/walrus_client.py": (
                "from importlib import import_module as load\n"
                "values = [(load := (lambda name: name))('orchard.sky.view') for _ in range(1)]\n"
                "after = load('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/comprehension_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(7, "orchard.sky.view"), (8, "orchard.sky.view"),
             (9, "orchard.sky.view")],
        )
        # A comprehension walrus target binds in the containing scope:
        # the later call is not safely attributable to the original import.
        walrus_sites = [site for site in impact["observed_sites"]
                        if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                        and site["path"] == "src/orchard/earth/walrus_client.py"]
        self.assertEqual(walrus_sites, [])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_leftmost_comprehension_iterable_uses_enclosing_scope(self):
        # Python evaluates the first 'in' expression outside the implicit
        # comprehension scope. Its own target cannot shadow a helper there,
        # including in a class body. Body calls remain correctly shadowed.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/first_iter_client.py": (
                "from importlib import import_module as load\n"
                "import importlib as loader\n"
                "list_comp = [v for load in (load('orchard.sky.view'),) for v in (1,)]\n"
                "set_comp = {v for loader in (loader.import_module('orchard.sky.view'),) for v in (1,)}\n"
                "dict_comp = {v: v for load in (load('orchard.sky.view'),) for v in (1,)}\n"
                "gen_comp = (v for loader in (loader.import_module('orchard.sky.view'),) for v in (1,))\n"
                "bad_body = [load('orchard.sky.view') for load in (lambda x: x,)]\n"
                "class Holder:\n"
                "    from importlib import import_module as class_load\n"
                "    first_iter = [v for class_load in (class_load('orchard.sky.view'),) for v in (1,)]\n"
                "    bad_body = [class_load('orchard.sky.view') for v in (1,)]\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/first_iter_client.py"]
        self.assertEqual([(site["line"], site["expression"]) for site in sites],
                         [(3, "orchard.sky.view"), (4, "orchard.sky.view"),
                          (5, "orchard.sky.view"), (6, "orchard.sky.view"),
                          (10, "orchard.sky.view")])
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_exception_pattern_and_delete_bindings_do_not_forge_dynamic_imports(self):
        # Except aliases, match captures and del targets bind without
        # ast.Name(Store). They must not masquerade as import-helper calls.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/binding_client.py": (
                "from importlib import import_module as load\n"
                "from pkgutil import resolve_name as resolve\n"
                "import importlib as loader\n"
                "def except_shadow():\n"
                "    from importlib import import_module as local_load\n"
                "    try:\n"
                "        raise RuntimeError()\n"
                "    except RuntimeError as local_load:\n"
                "        return local_load('orchard.sky.view')\n"
                "def match_capture():\n"
                "    from pkgutil import resolve_name as local_resolve\n"
                "    match ['value']:\n"
                "        case [local_resolve]:\n"
                "            return local_resolve('orchard.sky.view:View')\n"
                "def match_star():\n"
                "    from importlib import import_module as local_load\n"
                "    match [1, 2]:\n"
                "        case [*local_load]:\n"
                "            return local_load('orchard.sky.view')\n"
                "def match_mapping():\n"
                "    import importlib as local_loader\n"
                "    match {'a': 1}:\n"
                "        case {'a': _, **local_loader}:\n"
                "            return local_loader.import_module('orchard.sky.view')\n"
                "def deleted_alias():\n"
                "    from importlib import import_module as local_load\n"
                "    del local_load\n"
                "    return local_load('orchard.sky.view')\n"
                "good = load('orchard.sky.view')\n"
                "good_resolve = resolve('orchard.sky.view:View')\n"
                "good_loader = loader.import_module('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/binding_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(29, "orchard.sky.view"), (30, "orchard.sky.view:View"),
             (31, "orchard.sky.view")],
        )
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_definition_time_expressions_use_enclosing_scope(self):
        # Function/lambda defaults and annotations, decorators, and class
        # headers run before entering the new scope. A parameter with the
        # same name must not erase a real outer-scope migration witness.
        # Unaliased dotted imports also bind their root package.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/definition_client.py": (
                "from importlib import import_module as load\n"
                "def defaulted(load, x=load('orchard.sky.view')):\n"
                "    return load('orchard.sky.view')\n"
                "@load('orchard.sky.view').decorator\n"
                "def decorated(load):\n"
                "    return load('orchard.sky.view')\n"
                "def annotated(x: load('orchard.sky.view')) -> load('orchard.sky.view'):\n"
                "    return x\n"
                "f = lambda load, x=load('orchard.sky.view'): load('orchard.sky.view')\n"
                "class Holder:\n"
                "    from importlib import import_module as class_load\n"
                "    @class_load('orchard.sky.view').decorator\n"
                "    def method(class_load):\n"
                "        return class_load('orchard.sky.view')\n"
                "    def default(self, class_load=class_load('orchard.sky.view')):\n"
                "        return class_load('orchard.sky.view')\n"
                "    nested = lambda class_load=class_load('orchard.sky.view'): class_load\n"
                "    class Child(class_load('orchard.sky.view').View):\n"
                "        pass\n"
                "    @class_load('orchard.sky.view').decorator\n"
                "    class Inner:\n"
                "        pass\n"
                "import importlib.util\n"
                "module = importlib.import_module('orchard.sky.view')\n"
                "import importlib.util as util_loader\n"
                "bad = util_loader.import_module('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/definition_client.py"]
        self.assertEqual(sorted(site["line"] for site in sites),
                         sorted([2, 4, 7, 7, 9, 12, 15, 17, 18, 20, 24]))
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_global_nonlocal_mutations_invalidate_outer_helper_bindings(self):
        # global/nonlocal directives redirect writes into an enclosing scope.
        # Static evidence must not claim a known helper after such a write.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/directive_client.py": (
                "from importlib import import_module as module_load\n"
                "from importlib import import_module as keep\n"
                "def global_writer():\n"
                "    global module_load\n"
                "    module_load = lambda name: name\n"
                "def global_reader():\n"
                "    global module_load\n"
                "    return module_load('orchard.sky.view')\n"
                "def outer():\n"
                "    from importlib import import_module as nested_load\n"
                "    def mutate():\n"
                "        nonlocal nested_load\n"
                "        nested_load = lambda name: name\n"
                "    return nested_load('orchard.sky.view')\n"
                "def safe_outer():\n"
                "    from importlib import import_module as read_only\n"
                "    def inner():\n"
                "        nonlocal read_only\n"
                "        return read_only('orchard.sky.view')\n"
                "    return inner()\n"
                "positive = keep('orchard.sky.view')\n"
            ),
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        sites = [site for site in impact["observed_sites"]
                 if site["kind"] == "DYNAMIC_IMPORT_LITERAL"
                 and site["path"] == "src/orchard/earth/directive_client.py"]
        self.assertEqual(
            [(site["line"], site["expression"]) for site in sites],
            [(19, "orchard.sky.view"), (21, "orchard.sky.view")],
        )
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")


    def test_no_question_means_no_candidate(self):
        inv, scenarios, sources = setup(edges=())
        self.assertEqual(scenarios["candidates"], [])
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["rejected_scenarios"], [])
        self.assertEqual(report["decision"], "NOT_EVALUATED")

    def test_namespace_collision_with_package_initializer_blocks(self):
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/view/__init__.py": "x = 1\n",
        })
        self.assertEqual(len(scenarios["candidates"]), 1)
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        self.assertEqual(impact["cost_band"], "BLOCKED")
        self.assertEqual(impact["compatibility_status"], "BLOCKED")
        self.assertEqual(impact["namespace_collisions"], ["orchard.earth.view"])

    def test_namespace_directory_shadows_child_imports_even_without_init(self):
        # B4 sees an unoccupied view.py target, but creating that module can
        # shadow the existing namespace directory and its importable child.
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/view/child.py": "value = 1\n",
        })
        self.assertEqual(len(scenarios["candidates"]), 1)
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        self.assertEqual(impact["namespace_collisions"], ["orchard.earth.view"])
        self.assertEqual(impact["cost_band"], "BLOCKED")
        self.assertEqual(impact["compatibility_status"], "BLOCKED")
        self.assertIn("DOTTED_MODULE_NAMESPACE_COLLISION", impact["unknowns"])

    def test_similarly_named_sibling_directory_is_not_namespace_collision(self):
        inv, scenarios, sources = setup(extra={
            "src/orchard/earth/view_helpers/child.py": "value = 1\n",
        })
        impact = assess_architecture_migration(inv, scenarios, sources)["candidates"][0]
        self.assertEqual(impact["namespace_collisions"], [])
        self.assertNotEqual(impact["cost_band"], "BLOCKED")

    def test_unread_inventory_paths_downgrade_migration_confidence(self):
        # B1 may track a Python consumer without its source bytes. An unread
        # file cannot establish the absence of migration/API references.
        missing_path = "tests/unread_external.py"
        inv, scenarios, sources = setup(
            extra={missing_path: "from orchard.sky.view import View\n"},
            missing=(missing_path,),
        )
        self.assertEqual(len(scenarios["candidates"]), 1)
        unread = next(item for item in inv["files"]
                      if item["path"] == missing_path)
        self.assertEqual(unread["read_state"], "MISSING")
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual(report["source_coverage"]["missing_read_source_texts"], [])
        impact = report["candidates"][0]
        self.assertIn("INVENTORY_UNREAD_PATHS", impact["unknowns"])
        self.assertEqual(impact["confidence"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(impact["compatibility_status"], "NOT_EVALUATED")

    def test_missing_sources_do_not_claim_zero_external_references(self):
        inv, scenarios, sources = setup(extra={
            "tests/test_external.py": "from orchard.sky.view import View\n",
        })
        partial = dict(sources)
        partial.pop("tests/test_external.py")
        report = assess_architecture_migration(inv, scenarios, partial)
        self.assertIn("tests/test_external.py",
                      report["source_coverage"]["missing_read_source_texts"])
        self.assertEqual(report["candidates"][0]["confidence"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("SOURCE_COVERAGE_GAPS", report["candidates"][0]["unknowns"])

    def test_mismatched_hash_or_tampered_scenario_rejected(self):
        inv, scenarios, sources = setup()
        bad = dict(sources)
        bad["src/orchard/sky/view.py"] = "pass\n"
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, scenarios, bad)
        altered = deepcopy(scenarios)
        altered["candidates"][0]["path_mapping"][0]["to"] = "src/orchard/earth/fake.py"
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, altered, sources)
        altered = deepcopy(scenarios)
        altered["snapshot_sha"] = "0" * 40
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, altered, sources)

    def test_unread_moved_source_rejected_and_parser_gap_reported(self):
        inv, scenarios, sources = setup()
        bad = dict(sources)
        bad.pop("src/orchard/sky/view.py")
        with self.assertRaises(ArchitectureMigrationError):
            assess_architecture_migration(inv, scenarios, bad)
        inv, scenarios, sources = setup(extra={
            "tests/broken.py": "def bad(:\n",
        })
        report = assess_architecture_migration(inv, scenarios, sources)
        self.assertEqual(report["source_coverage"]["python_parse_failures"],
                         ["tests/broken.py"])
        self.assertEqual(report["candidates"][0]["confidence"], "INSUFFICIENT_EVIDENCE")

    def test_renamed_isomorphic_package_not_preseeded(self):
        new_sources = {
            p.replace("orchard", "woodland"): value.replace("orchard", "woodland")
            for p, value in SOURCES.items()
        }
        new_sources["src/woodland/sky/view.py"] = (
            "from woodland.earth.model import Model\nclass View: pass\n"
        )
        policy = deepcopy(POLICY)
        policy["scope"] = "src/woodland"
        from codeqa.core.dependency import StaticDependency
        edges = tuple(StaticDependency(
            e.source_path.replace("orchard", "woodland"),
            e.target_path.replace("orchard", "woodland"),
            e.line, e.expression.replace("orchard", "woodland"), e.execution,
        ) for e in CONCENTRATED)
        inventory = analyze_architecture_inventory(SHA, sorted(new_sources),
                                                    new_sources, policy)
        graph = DependencyGraph(SHA, tuple(sorted(new_sources)), (), edges, ())
        metrics = analyze_architecture_metrics(inventory, graph, policy, PROFILE)
        opp = discover_architecture_opportunities(inventory, metrics)
        scenarios = generate_virtual_layout_scenarios(inventory, metrics, opp, policy)
        report = assess_architecture_migration(inventory, scenarios, new_sources)
        self.assertEqual(len(report["candidates"]), 1)
        self.assertEqual(report["candidates"][0]["path_mapping"][0]["to"],
                         "src/woodland/earth/view.py")
        self.assertIn("EXTERNAL_CONSUMERS_UNOBSERVED",
                      report["candidates"][0]["unknowns"])


if __name__ == "__main__":
    unittest.main()
