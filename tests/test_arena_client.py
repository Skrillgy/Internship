import asyncio
import random
from uuid import uuid4

import httpx
import pytest

from app.fleet import generate_fleet
from arena.client import ServiceClient, ServiceError

SESSION_ID = str(uuid4())

def test_all_contract_endpoints():
    fleet = generate_fleet(random.Random(42))
    requests = []

    def handler(request):
        requests.append(request)

        responses = {
            '/game': (201, {'session_id': SESSION_ID, 'ships': fleet}),
            f'/game/{SESSION_ID}/shot': (200, {'coordinate': 'D7'}),
            f'/game/{SESSION_ID}/opponent-shot': (200, {'result': 'hit'}),
            f'/game/{SESSION_ID}/shot/result': (200, {'status': 'accepted'}),
            f'/game/{SESSION_ID}/close': (200, {'status': 'closed'})
        }

        status_code, body = responses[request.url.path]

        return httpx.Response(status_code, json=body)

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            game = await client.start_game()

            assert game['session_id'] == SESSION_ID
            assert game['ships'] == fleet

            assert await client.make_shot(SESSION_ID) == 'D7'
            assert await client.opponent_shot(SESSION_ID, 'D7') == 'hit'

            await client.report_result(SESSION_ID, 'hit')
            await client.close_game(SESSION_ID)

    asyncio.run(run())

    assert len(requests) == 5
    assert all(request.method == 'POST' for request in requests)

    assert requests[0].content == b''
    assert requests[1].content == b''
    assert requests[2].content == b'{"coordinate":"D7"}'
    assert requests[3].content == b'{"result":"hit"}'
    assert requests[4].content == b''

@pytest.mark.parametrize(
    ('method', 'body'),
    [
        ('start_game', {'session_id': 'wrong', 'ships': []}),
        ('start_game', {'session_id': SESSION_ID, 'ships': []}),
        ('make_shot', {'coordinate': 'K1'}),
        ('make_shot', {'coordinate': 'A1', 'extra': True}),
        ('opponent_shot', {'result': 'boom'}),
        ('opponent_shot', {'result': []}),
        ('report_result', {'status': 'ignored'}),
        ('close_game', {'status': 'active'})
    ]
)
def test_invalid_contract_response_is_rejected(method, body):
    def handler(request):
        status_code = 201 if method == 'start_game' else 200
        return httpx.Response(status_code, json=body)

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ServiceError):
                if method == 'start_game':
                    await client.start_game()
                elif method == 'make_shot':
                    await client.make_shot(SESSION_ID)
                elif method == 'opponent_shot':
                    await client.opponent_shot(SESSION_ID, 'A1')
                elif method == 'report_result':
                    await client.report_result(SESSION_ID, 'hit')
                else:
                    await client.close_game(SESSION_ID)

    asyncio.run(run())

@pytest.mark.parametrize('status_code', [302, 404, 409, 500])
def test_unexpected_http_status_is_rejected(status_code):
    def handler(request):
        return httpx.Response(status_code, json={'detail': 'Test error'})

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ServiceError, match='HTTP'):
                await client.make_shot(SESSION_ID)

    asyncio.run(run())

@pytest.mark.parametrize('content', [b'not JSON', b'[]'])
def test_invalid_json_response_is_rejected(content):
    def handler(request):
        return httpx.Response(200, content=content)

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ServiceError):
                await client.make_shot(SESSION_ID)

    asyncio.run(run())

def test_timeout_is_rejected():
    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={'coordinate': 'A1'})

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ServiceError, match='timeout'):
                await client.make_shot(SESSION_ID)

    asyncio.run(run())

def test_connection_failune_is_rejected():
    def handler(request):
        raise httpx.ConnectError('Connection refused', request=request)

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ServiceError, match='communication'):
                await client.make_shot(SESSION_ID)

    asyncio.run(run())

def test_invalid_fleet_keeps_session_id_for_cleanup():
    requests = []

    def handler(request):
        requests.append(request.url.path)

        if request.url.path == '/game':
            return httpx.Response(201, json={'session_id': SESSION_ID, 'ships': []})

        if request.url.path == f'/game/{SESSION_ID}/close':
            return httpx.Response(200, json={'status': 'closed'})

        return httpx.Response(404)

    async def run():
        async with ServiceClient('http://localhost:8001', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ServiceError, match='Invalid fleet'):
                await client.start_game()

            assert client.created_session_id == SESSION_ID

            await client.close_game(client.created_session_id)

    asyncio.run(run())

    assert requests == [
        '/game',
        f'/game/{SESSION_ID}/close'
    ]