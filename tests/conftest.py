import os
import sys

sys.path.insert(0, os.path.abspath(os.getcwd()))

import pytest
import asyncio
import gc
import psycopg2
import socket
import uuid
import time

from docker import Client as DockerClient

import aiopg
from aiopg import sa


@pytest.fixture(scope='session')
def unused_port():
    def f():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]
        return f


@pytest.yield_fixture
def loop(request):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    yield loop

    if not loop._closed:
        loop.call_soon(loop.stop)
        loop.run_forever()
        loop.close()

    gc.collect()
    asyncio.set_event_loop(None)


@pytest.fixture(scope='session')
def docker():
    return DockerClient(version='auto')


@pytest.fixture(scope='session')
def session_id():
    return str(uuid.uuid4())


@pytest.yield_fixture(scope='session')
def pg_server(unused_port, docker, session_id, request):
    pg_tag = '9.5'
    # if not request.config.option.no_pull:
    docker.pull('postgres:{}'.format(pg_tag))
    
    container = docker.create_container(
        image='postgres:{}'.format(pg_tag),
        name='aiopg-test-server-{}-{}'.format(pg_tag, session_id),
        ports=[5432],
        detach=True
    )

    print(container)
    docker.start(container=container['Id'])

    inspection = docker.inspect_container(container['Id'])
    host = inspection['NetworkSettings']['IPAddress']
    print(host)
    pg_params = dict(
        database='postgres',
        user='postgres',
        password='mysecretpassword',
        host=host,
        port=5432,
    )

    delay = 0.001

    for i in range(100):
        try:
            conn = psycopg2.connect(**pg_params)
            cur = conn.cursor()
            cur.execute('CREATE EXTENSION hstore;')
            cur.close()
            conn.close()
            break
        except psycopg2.Error:
            time.sleep(delay)
            delay *= 2
    else:
        pytest.fail('Cannot start postgres server')

    container['host'] = host
    container['port'] = 5432
    container['pg_params'] = pg_params

    yield container

    docker.kill(container['Id'])
    docker.remove_container(container['Id'])


@pytest.fixture
def pg_params(pg_server):
    return dict(**pg_server['pg_params'])


@pytest.yield_fixture()
def make_connection(loop, pg_params):
    conn = None

    async def go(*, no_loop=False, **kwargs):
        nonlocal conn
        params = pg_params.copy()
        params.update(kwargs)
        useloop = None if no_loop else loop
        conn = await aiopg.connect(loop=useloop, **params)
        return conn

    yield go

    if conn is not None:
        loop.run_until_complete(conn.close())


@pytest.fixture
def connect(make_connection):
    async def go(**kwargs):
        conn = await make_connection(**kwargs)
        return conn
    return go

