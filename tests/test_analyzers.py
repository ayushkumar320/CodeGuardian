import os

from codeguardian.analyzers import imports as imports_analyzer
from codeguardian.analyzers import tests as tests_analyzer
from codeguardian.models import DiffFile, FileCategory, FileStatus


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_dependency_blast_radius(tmp_path):
    root = str(tmp_path)
    _write(root, "src/util.ts", "export const x = 1;")
    _write(root, "src/a.ts", "import { x } from './util';")
    _write(root, "src/b.ts", "import { x } from './util';")

    changed = [DiffFile(path="src/util.ts", status=FileStatus.modified,
                        category=FileCategory.backend)]
    findings = imports_analyzer.analyze(root, changed, high_risk_paths=[])
    assert len(findings) == 1
    f = findings[0]
    assert "src/a.ts" in f.evidence_files
    assert "src/b.ts" in f.evidence_files


def test_high_risk_path_flagged_even_without_dependents(tmp_path):
    root = str(tmp_path)
    _write(root, "src/api/profile/route.ts", "export const GET = () => {};")
    changed = [DiffFile(path="src/api/profile/route.ts", status=FileStatus.modified,
                        category=FileCategory.backend)]
    findings = imports_analyzer.analyze(root, changed, high_risk_paths=["**/api/**"])
    assert findings and findings[0].category.value == "dependency"


def test_missing_test_recommendation(tmp_path):
    root = str(tmp_path)
    _write(root, "src/service.ts", "export const f = () => {};")
    changed = [DiffFile(path="src/service.ts", status=FileStatus.modified,
                        category=FileCategory.backend)]
    findings = tests_analyzer.analyze(root, changed)
    assert findings and findings[0].category.value == "test"


def test_present_test_suppresses_recommendation(tmp_path):
    root = str(tmp_path)
    _write(root, "src/service.ts", "export const f = () => {};")
    _write(root, "src/service.test.ts", "test('f', () => {});")
    changed = [DiffFile(path="src/service.ts", status=FileStatus.modified,
                        category=FileCategory.backend)]
    findings = tests_analyzer.analyze(root, changed)
    assert findings == []
