import pytest

from sql_query.query_safety import validate_select_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users",
        "select id, name from users where id = 1",
        "WITH recent AS (SELECT * FROM users) SELECT * FROM recent",
        "SELECT 1 -- trailing comment",
    ],
)
def test_valid_select_statements_pass(sql):
    validate_select_only(sql)  # should not raise


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users (name) VALUES ('x')",
        "UPDATE users SET name = 'x'",
        "DELETE FROM users",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN x TEXT",
        "CREATE TABLE evil (id INTEGER)",
    ],
)
def test_non_select_statements_are_rejected(sql):
    with pytest.raises(ValueError, match="Only SELECT"):
        validate_select_only(sql)


def test_multiple_statements_are_rejected_even_if_first_is_select():
    with pytest.raises(ValueError, match="single SQL statement"):
        validate_select_only("SELECT * FROM users; DROP TABLE users;")


def test_empty_input_is_rejected():
    with pytest.raises(ValueError, match="No SQL statement"):
        validate_select_only("   ")
