from codeguardian.analyzers import api as api_analyzer
from codeguardian.analyzers import architecture as arch_analyzer
from codeguardian.analyzers import database as db_analyzer
from codeguardian.models import DiffFile, FileCategory, FileStatus
from codeguardian.policy import Architecture, ForbiddenImport


def _f(path, category, patch=None, status=FileStatus.modified):
    return DiffFile(path=path, status=status, category=category, patch=patch)


def test_api_removed_handler_is_high():
    patch = "--- a/src/api/profile/route.ts\n+++ b\n-export async function GET() {}\n+// removed\n"
    findings = api_analyzer.analyze(".", [_f("src/api/profile/route.ts", FileCategory.backend, patch)])
    assert findings and findings[0].severity.value == "high"
    assert findings[0].category.value == "api"


def test_api_plain_change_is_medium():
    patch = "--- a\n+++ b\n+const z = 1;\n"
    findings = api_analyzer.analyze(".", [_f("src/api/profile/route.ts", FileCategory.backend, patch)])
    assert findings and findings[0].severity.value == "medium"


def test_database_destructive_is_critical():
    patch = "--- a\n+++ b\n+DROP TABLE users;\n"
    findings = db_analyzer.analyze(".", [_f("db/migrations/002.sql", FileCategory.database, patch)])
    assert findings and findings[0].severity.value == "critical"


def test_database_schema_without_migration_is_high():
    patch = "--- a\n+++ b\n+model User { id Int }\n"
    findings = db_analyzer.analyze(".", [_f("prisma/schema.prisma", FileCategory.database, patch)])
    titles = [f.title for f in findings]
    assert any("without a migration" in t for t in titles)


def test_architecture_forbidden_import(tmp_path):
    p = tmp_path / "src" / "components"
    p.mkdir(parents=True)
    (p / "Button.tsx").write_text("import { db } from '../server/db';\n")
    arch = Architecture(forbidden_imports=[
        ForbiddenImport(paths="**/components/**", cannot_import="server", reason="UI must not touch server")
    ])
    findings = arch_analyzer.analyze(str(tmp_path),
                                     [_f("src/components/Button.tsx", FileCategory.frontend)], arch)
    assert findings and findings[0].category.value == "architecture"


def test_architecture_no_rules_no_findings():
    findings = arch_analyzer.analyze(".", [_f("a.ts", FileCategory.backend)], Architecture())
    assert findings == []
