import os

from codeguardian.analyzers import api as api_analyzer
from codeguardian.analyzers import architecture as arch_analyzer
from codeguardian.analyzers import database as db_analyzer
from codeguardian.analyzers import tests as tests_analyzer
from codeguardian.analyzers import types as types_analyzer
from codeguardian.models import DiffFile, FileCategory, FileStatus
from codeguardian.policy import Architecture, Layer
from codeguardian.policy import TestSuite as SuiteMap


def _f(path, category, patch=None):
    return DiffFile(path=path, status=FileStatus.modified, category=category, patch=patch)


def _w(root, rel, content):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)


# --- shared types ---------------------------------------------------------
def test_types_removed_export_with_blast_radius(tmp_path):
    root = str(tmp_path)
    _w(root, "src/types/user.types.ts", "export type User = { id: number };\n")
    _w(root, "src/a.ts", "import { User } from './types/user.types';\n")
    _w(root, "src/b.ts", "import { User } from './types/user.types';\n")
    patch = "--- a\n+++ b\n-export type User = { id: number };\n+export type Account = {};\n"
    findings = types_analyzer.analyze(root, [_f("src/types/user.types.ts", FileCategory.types, patch)])
    assert findings
    assert "src/a.ts" in findings[0].evidence_files


# --- database deepened ----------------------------------------------------
def test_prisma_field_removal_is_high():
    patch = "--- a\n+++ b\n model User {\n-  email String\n }\n"
    findings = db_analyzer.analyze(".", [_f("prisma/schema.prisma", FileCategory.database, patch)])
    assert findings and findings[0].severity.value in ("high", "critical")


def test_sql_alter_column_type_destructive():
    patch = "--- a\n+++ b\n+ALTER TABLE users ALTER COLUMN age TYPE bigint;\n"
    findings = db_analyzer.analyze(".", [_f("db/migrations/003.sql", FileCategory.database, patch)])
    assert findings and findings[0].severity.value == "critical"


# --- API spec drift -------------------------------------------------------
def test_graphql_removed_type_is_drift():
    patch = "--- a\n+++ b\n-type User {\n-  id: ID\n-}\n"
    findings = api_analyzer.analyze(".", [_f("schema.graphql", FileCategory.other, patch)])
    assert findings and "drift" in findings[0].title.lower()


def test_api_response_field_removed():
    patch = "--- a/src/api/u/route.ts\n+++ b\n   return Response.json({\n-    email: user.email,\n   })\n"
    findings = api_analyzer.analyze(".", [_f("src/api/u/route.ts", FileCategory.backend, patch)])
    assert findings and findings[0].severity.value == "high"


# --- architecture: layers + cycles ---------------------------------------
def test_layer_violation(tmp_path):
    root = str(tmp_path)
    _w(root, "src/ui/Page.tsx", "import { q } from '../data/db';\nexport const P=1;\n")
    _w(root, "src/data/db.ts", "export const q=1;\n")
    arch = Architecture(layers=[
        Layer(name="ui", paths="**/ui/**", may_import=["shared"]),
        Layer(name="data", paths="**/data/**"),
    ])
    findings = arch_analyzer.analyze(root, [_f("src/ui/Page.tsx", FileCategory.frontend)], arch)
    assert any("Layer violation" in f.title for f in findings)


def test_circular_dependency(tmp_path):
    root = str(tmp_path)
    _w(root, "src/a.ts", "import './b';\nexport const a=1;\n")
    _w(root, "src/b.ts", "import './a';\nexport const b=1;\n")
    findings = arch_analyzer.analyze(root, [_f("src/a.ts", FileCategory.backend)],
                                     Architecture(detect_circular=True))
    assert any("Circular dependency" in f.title for f in findings)


# --- tests: import-graph impact + suites ----------------------------------
def test_impacted_tests_detected(tmp_path):
    root = str(tmp_path)
    _w(root, "src/service.ts", "export const f=()=>1;\n")
    _w(root, "src/service.spec.ts", "import { f } from './service';\n")
    findings = tests_analyzer.analyze(root, [_f("src/service.ts", FileCategory.backend)])
    assert findings and "impacted by" in findings[0].title


def test_suite_mapping_recommended(tmp_path):
    root = str(tmp_path)
    _w(root, "src/billing/charge.ts", "export const c=()=>1;\n")
    mappings = [SuiteMap(paths="**/billing/**", suite="billing-integration")]
    findings = tests_analyzer.analyze(root, [_f("src/billing/charge.ts", FileCategory.backend)], mappings)
    assert any("billing-integration" in a for f in findings for a in f.recommended_actions)
