"""Verify DB driver dependencies are optional extras, not core requirements."""
import importlib.metadata


def _pkg_name(req: str) -> str:
    """Extract the package name from a Requires-Dist string (strip version/markers)."""
    return req.split(';')[0].split('>=')[0].split('==')[0].split('[')[0].strip().lower()


def test_mysql_connector_not_in_core_deps():
    dist = importlib.metadata.distribution('binctl')
    requires = dist.metadata.get_all('Requires-Dist') or []
    core_names = {_pkg_name(r) for r in requires if 'extra ==' not in r}
    assert 'mysql-connector-python' not in core_names


def test_pymysql_in_mysql_extra():
    dist = importlib.metadata.distribution('binctl')
    requires = dist.metadata.get_all('Requires-Dist') or []
    mysql_extras = [r for r in requires if 'extra == "mysql"' in r]
    names = {_pkg_name(r) for r in mysql_extras}
    assert 'pymysql' in names


def test_psycopg2_in_postgresql_extra():
    dist = importlib.metadata.distribution('binctl')
    requires = dist.metadata.get_all('Requires-Dist') or []
    pg_extras = [r for r in requires if 'extra == "postgresql"' in r]
    names = {_pkg_name(r) for r in pg_extras}
    assert 'psycopg2-binary' in names
