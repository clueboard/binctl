import ast
from pathlib import Path


def test_sqlalchemy_queries_stay_in_db_package():
    """Application layers must call DB functions instead of constructing SQL."""
    server = Path(__file__).parent.parent / 'binctl_server'
    violations = []
    for path in server.rglob('*.py'):
        if path.parent.name == 'db':
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'sqlalchemy':
                imported = {alias.name for alias in node.names}
                if 'text' in imported:
                    violations.append(f'{path.relative_to(server)}:{node.lineno} imports sqlalchemy.text')
            if isinstance(node, ast.Import) and any(alias.name == 'sqlalchemy' for alias in node.names):
                violations.append(f'{path.relative_to(server)}:{node.lineno} imports sqlalchemy')
    assert violations == []
