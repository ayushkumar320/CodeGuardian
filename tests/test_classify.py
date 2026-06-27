from codeguardian.pr.classify import classify, is_docs_only
from codeguardian.models import FileCategory


def test_classify_categories():
    assert classify("README.md") == FileCategory.docs
    assert classify("prisma/schema.prisma") == FileCategory.database
    assert classify("db/migrations/001_init.sql") == FileCategory.database
    assert classify("src/api/profile/route.ts") == FileCategory.backend
    assert classify("src/components/Button.tsx") == FileCategory.frontend
    assert classify("src/user.test.ts") == FileCategory.test
    assert classify("src/models.types.ts") == FileCategory.types
    assert classify("package.json") == FileCategory.config


def test_is_docs_only():
    assert is_docs_only([FileCategory.docs, FileCategory.docs])
    assert not is_docs_only([FileCategory.docs, FileCategory.backend])
    assert not is_docs_only([])
