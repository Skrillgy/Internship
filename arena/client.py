import asyncio
import json
from uuid import UUID

import httpx

from app.fleet import parse_coordinate, validate_fleet

class ServiceError(Exception):
    """Сервис недоступен или нарушил контракт."""

class ServiceClient:
    def __init__(self, base_url:str, *, timeout:float = 1.0, transport: httpx.AsyncBaseTransport | None = None):
        if timeout <= 0:
            raise ValueError('Timeout must be positive')

        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.created_session_id: str | None = None
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport
        )

    async def __aenter__(self):
        await self._http.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._http.__aexit__(exc_type, exc_value, traceback)

    async def _request(self, path: str, expected_status: int, body: dict | None = None) -> dict:
        request_options = {}

        if body is not None:
            request_options['json'] = body

        try:
            async with asyncio.timeout(self.timeout):
                async with self._http.stream('POST', path, **request_options) as response:
                    if response.status_code != expected_status:
                        raise ServiceError(
                            f'{path}: expected HTTP {expected_status}, '
                            f'got {response.status_code}'
                        )

                    chunks = []
                    size = 0

                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 64 * 1024:
                            raise ServiceError(f'{path}: response too large')
                        chunks.append(chunk)

                raw_body = b''.join(chunks)

        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ServiceError(f'{path}: timeout after {self.timeout:g} seconds') from exc

        except httpx.HTTPError as exc:
            raise ServiceError(f'{path}: HTTP communication failed') from exc

        try:
            data = json.loads(raw_body)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ServiceError(f'{path}: invalid JSON response') from exc

        if not isinstance(data, dict):
            raise ServiceError(f'{path}: response must be a JSON object')

        return data

    @staticmethod
    def _check_fields(data: dict, expected: set[str]) -> None:
        if set(data) != expected:
            raise ServiceError(f'Unexpected response fields: {list(data)}')

    async def start_game(self) -> dict:
        self.created_session_id = None

        data = await self._request('/game', 201)
        session_id = data.get('session_id')

        if not isinstance(session_id, str):
            raise ServiceError('session_id must be a UUID string')

        try:
            UUID(session_id)
        except ValueError as exc:
            raise ServiceError('Invalid session_id UUID') from exc

        self.created_session_id = session_id
        self._check_fields(data, {'session_id', 'ships'})

        if not validate_fleet(data['ships']):
            raise ServiceError('Invalid fleet')

        return data

    async def make_shot(self, session_id: str) -> str:
        data = await self._request(f'/game/{session_id}/shot', 200)
        self._check_fields(data, {'coordinate'})

        try:
            parse_coordinate(data['coordinate'])
        except ValueError as exc:
            raise ServiceError('Invalid shot coordinate') from exc

        return data['coordinate']

    async def opponent_shot(self, session_id: str, coordinate: str) -> str:
        data = await self._request(f'/game/{session_id}/opponent-shot', 200, {'coordinate': coordinate})
        self._check_fields(data, {'result'})

        result = data['result']

        if not isinstance(result, str):
            raise ServiceError('Shot result must be a string')

        if result not in {'miss', 'hit', 'killed'}:
            raise ServiceError('Invalid shot result')

        return result

    async def report_result(self, session_id: str, result: str) -> None:
        data = await self._request(f'/game/{session_id}/shot/result', 200, {'result': result})
        self._check_fields(data, {'status'})

        if data['status'] != 'accepted':
            raise ServiceError('Shot result was not accepted')

    async def close_game(self, session_id: str) -> None:
        data = await self._request(f'/game/{session_id}/close', 200)
        self._check_fields(data, {'status'})

        if data['status'] != 'closed':
            raise ServiceError('Session was not closed')