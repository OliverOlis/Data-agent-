import pytest

from executor import QueryError, SQLiteExecutor
from policy import SecurityPolicy


def test_select_result_and_limits(tmp_path):
    db = tmp_path / "x.db"
    c = __import__("sqlite3").connect(db)
    c.execute("create table sales(id integer, event_time text)")
    c.executemany("insert into sales values (?, ?)", [(i, "2026-01-01") for i in range(4)])
    c.commit(); c.close()
    ex = SQLiteExecutor(str(db), SecurityPolicy.create(allowed_tables={"sales"}, max_rows=2))
    out = ex.execute("select id from sales where event_time >= :t", {"t": "2026-01-01"})
    assert out.row_count == 2 and out.truncated


def test_blocks_mutation_and_multiple_statements(tmp_path):
    ex = SQLiteExecutor(":memory:")
    with pytest.raises(QueryError) as e:
        ex.execute("delete from x")
    assert e.value.code in {"read_only", "forbidden_syntax"}
    with pytest.raises(QueryError) as e:
        ex.execute("select 1; select 2")
    assert e.value.code == "multiple_statements"
