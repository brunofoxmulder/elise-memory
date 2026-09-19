import os
from pathlib import Path

from elise_memory.__main__ import main


ROOT = Path(__file__).resolve().parents[1]
SHIPPED_APP = ROOT / "elise-memory" / "app"
SHIPPED_PACKAGE = SHIPPED_APP / "elise_memory"


def test_main_uses_safe_runtime_defaults(monkeypatch):
    seen = {}
    monkeypatch.delenv("ELISE_MEMORY_HOST", raising=False)
    monkeypatch.delenv("ELISE_MEMORY_PORT", raising=False)
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app, host, port: seen.update(app=app, host=host, port=port),
    )
    main()
    assert seen == {
        "app": "elise_memory.app:app",
        "host": "0.0.0.0",
        "port": 8099,
    }


def test_repository_has_one_python_source_tree():
    """The package shipped by HA is the only elise_memory source tree."""
    assert SHIPPED_PACKAGE.is_dir()
    assert not (ROOT / "elise_memory").exists()


def test_shipped_runtime_contains_all_local_imports():
    import ast

    missing_imports = set()
    for path in SHIPPED_PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                top = node.module.split(".", 1)[0]
                if (
                    not (SHIPPED_PACKAGE / f"{top}.py").exists()
                    and not (SHIPPED_PACKAGE / top / "__init__.py").exists()
                ):
                    missing_imports.add(top)
    assert not missing_imports, (
        f"HA app runtime has unresolved local imports: {sorted(missing_imports)}"
    )


def test_dev13_version_is_aligned_across_shipped_artifacts():
    from elise_memory import __version__
    from elise_memory.app import app

    assert __version__ == "0.1.0-dev.13"
    assert app.version == "0.1.0-dev.13"

    manifest = (ROOT / "elise-memory" / "config.yaml").read_text(encoding="utf-8")
    pyproject = (SHIPPED_APP / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version: "0.1.0-dev.13"' in manifest
    assert 'version = "0.1.0-dev.13"' in pyproject
