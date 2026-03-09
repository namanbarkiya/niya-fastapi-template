"""
Product isolation enforcement.

These tests statically verify that no product module imports from any
other product module. This is a hard architectural rule from CLAUDE.md:

  "Product modules never import from each other."

Uses the `ast` module to parse imports without executing the code.
Runs entirely at collection time — no DB needed, no fixtures.
"""
import ast
import os
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_PRODUCTS_DIR = Path(__file__).parent.parent / "app" / "products"

# All registered product package names
_PRODUCT_NAMES: list[str] = [
    d.name for d in _PRODUCTS_DIR.iterdir()
    if d.is_dir() and not d.name.startswith("_")
]


# ─────────────────────────────────────────────────────────────────────────────
# AST helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_imports(source: str) -> list[str]:
    """
    Return all imported module names from a Python source string.
    Handles both `import x.y` and `from x.y import z`.
    """
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _get_python_files(product_name: str) -> list[Path]:
    product_dir = _PRODUCTS_DIR / product_name
    return list(product_dir.rglob("*.py"))


def _cross_product_violations(product_name: str) -> list[str]:
    """
    Scan all .py files in `product_name` for imports from sibling products.
    Returns a list of violation strings for reporting.
    """
    other_products = [p for p in _PRODUCT_NAMES if p != product_name]
    violations: list[str] = []

    for py_file in _get_python_files(product_name):
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue

        imported_modules = _get_imports(source)
        for module in imported_modules:
            for other in other_products:
                # Check for "app.products.other_product" in any import path
                if f"app.products.{other}" in module:
                    violations.append(
                        f"  {py_file.relative_to(_PRODUCTS_DIR.parent.parent)}"
                        f"\n    imports from '{module}' (product: {other})"
                    )
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# Tests — one per product, parameterised so failures name the product
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("product_name", _PRODUCT_NAMES)
def test_product_has_no_cross_product_imports(product_name: str):
    """
    Ensure no file in app/products/<product_name>/ imports from any
    other product module (app.products.<other>.*).
    """
    violations = _cross_product_violations(product_name)
    assert not violations, (
        f"Product '{product_name}' has forbidden cross-product imports:\n"
        + "\n".join(violations)
        + "\n\nFix: products must NEVER import from sibling products. "
        "Use shared repos for cross-domain data access."
    )


def test_all_products_discovered():
    """Sanity check that we found at least the expected products."""
    assert "product_alpha" in _PRODUCT_NAMES, (
        "product_alpha not found in app/products/. "
        "Check that _PRODUCTS_DIR is pointing at the right location."
    )
    assert "taskboard" in _PRODUCT_NAMES


def test_shared_module_not_treated_as_product():
    """The 'shared' directory is not a product — it must not appear in the list."""
    assert "shared" not in _PRODUCT_NAMES


# ─────────────────────────────────────────────────────────────────────────────
# Additional structural checks
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("product_name", _PRODUCT_NAMES)
def test_product_has_required_subdirectories(product_name: str):
    """Every product must have the standard module structure."""
    product_dir = _PRODUCTS_DIR / product_name
    required = {"models", "repos", "schemas", "services", "routes"}
    existing = {d.name for d in product_dir.iterdir() if d.is_dir()}
    missing = required - existing
    assert not missing, (
        f"Product '{product_name}' is missing required subdirectories: {missing}"
    )


@pytest.mark.parametrize("product_name", _PRODUCT_NAMES)
def test_product_models_use_correct_schema(product_name: str):
    """
    Every SQLAlchemy model in a product must declare schema = product_name.
    Catches copy-paste mistakes where a model accidentally uses "shared".
    """
    models_dir = _PRODUCTS_DIR / product_name / "models"
    violations: list[str] = []

    for py_file in models_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        # Check for wrong schema declarations
        for wrong_schema in [s for s in _PRODUCT_NAMES + ["shared"] if s != product_name]:
            if f'"schema": "{wrong_schema}"' in source or f"'schema': '{wrong_schema}'" in source:
                violations.append(
                    f"  {py_file.name} uses schema='{wrong_schema}' "
                    f"but should use schema='{product_name}'"
                )

    assert not violations, (
        f"Product '{product_name}' has models with wrong schema declarations:\n"
        + "\n".join(violations)
    )
