import os

from elise_memory.__main__ import main


def test_main_uses_safe_runtime_defaults(monkeypatch):
    seen = {}
    monkeypatch.delenv("ELISE_MEMORY_HOST", raising=False)
    monkeypatch.delenv("ELISE_MEMORY_PORT", raising=False)
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: seen.update(app=app, host=host, port=port))
    main()
    assert seen == {"app": "elise_memory.app:app", "host": "0.0.0.0", "port": 8099}


def test_haos_vendored_runtime_contains_required_python_modules():
    """Keep the HAOS vendored runtime complete enough to import the application."""
    from pathlib import Path

    source_dir = Path(__file__).resolve().parents[1] / "elise_memory"
    vendored_dir = Path(__file__).resolve().parents[1] / "elise-memory" / "app" / "elise_memory"
    required = {
        "__init__.py",
        "__main__.py",
        "app.py",
        "models.py",
        "opening_context.py",
        "session.py",
        "temporal.py",
    }
    missing = sorted(name for name in required if not (vendored_dir / name).is_file())
    assert not missing, f"HAOS vendored runtime is missing: {missing}"

    # Every local elise_memory import used by the vendored runtime must resolve
    # to a vendored module/package, preventing another missing-module boot loop.
    import ast

    missing_imports = set()
    for path in vendored_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                top = node.module.split(".", 1)[0]
                if not (vendored_dir / f"{top}.py").exists() and not (vendored_dir / top / "__init__.py").exists():
                    missing_imports.add(top)
    assert not missing_imports, f"HAOS vendored runtime has unresolved local imports: {sorted(missing_imports)}"
