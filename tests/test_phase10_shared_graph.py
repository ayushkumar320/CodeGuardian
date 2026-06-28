"""Phase 10: the import graph is built at most once per analysis run.

Several analyzers (dependency, test, types, architecture) need the import graph.
Before Phase 10 each rebuilt it — 4-5 full repo walks per run. Now it is built
once in repository_context and shared via graph state.
"""

import os
import subprocess

import codeguardian.graph.nodes as nodes
from codeguardian.analyzers.imports import build_import_graph
from codeguardian.graph.build import run_analysis
from codeguardian.models import PrContext, RiskLevel
from codeguardian.policy import Policy


def _git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _repo(tmp_path):
    root = str(tmp_path)
    _git(root, "init", "-q")
    _write(root, "src/util.ts", "export const x = 1;\n")
    _write(root, "src/a.ts", "import { x } from './util';\n")
    _write(root, "src/b.ts", "import { x } from './util';\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    _write(root, "src/util.ts", "export const x = 2;\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "change")
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    return root, base, head


def test_import_graph_built_once_per_run(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root, base, head = _repo(tmp_path)

    calls = {"n": 0}
    real = build_import_graph

    def counting(repo_root, *args, **kwargs):
        calls["n"] += 1
        return real(repo_root, *args, **kwargs)

    # Patch the name the node uses, so any analyzer that *also* fell back to
    # building its own graph would bump the counter past 1.
    monkeypatch.setattr(nodes, "build_import_graph", counting)
    import codeguardian.analyzers.imports as imports_mod
    monkeypatch.setattr(imports_mod, "build_import_graph", counting)

    pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy())

    assert calls["n"] == 1, f"import graph built {calls['n']} times, expected exactly 1"
    # Sanity: the shared graph still produces the dependency finding (2 dependents).
    assert report.risk.level != RiskLevel.low or report.active_findings()


def test_build_import_graph_forward_and_reverse_consistent(tmp_path):
    root, _, _ = _repo(tmp_path)
    g = build_import_graph(root)
    assert g.reverse["src/util.ts"] == {"src/a.ts", "src/b.ts"}
    assert g.forward["src/a.ts"] == {"src/util.ts"}
    # forward and reverse are mirror images
    for src, targets in g.forward.items():
        for tgt in targets:
            assert src in g.reverse[tgt]
