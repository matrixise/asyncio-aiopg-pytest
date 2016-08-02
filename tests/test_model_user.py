import pytest

from events.models import User

def test_create_user(connect):
    conn = yield from connect()
    cur = yield from conn.cursor()
    yield from cur.execute('SELECT version()')
    ret = yield from cur.fetchone()
    print(ret)
