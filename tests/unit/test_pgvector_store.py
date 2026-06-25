from app.infrastructure.databases.vector.pgvector import _read_count


def test_read_count_supports_dict_rows() -> None:
    assert _read_count({"count": 3}) == 3


def test_read_count_supports_tuple_rows() -> None:
    assert _read_count((4,)) == 4
