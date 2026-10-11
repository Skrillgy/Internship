import asyncio
import json
import random
from uuid import uuid4

import httpx
import pytest

from app.fleet import generate_fleet
from arena.board import Board
from arena.client import ServiceClient
from arena.match import run_match

def play_test_match(
        *,
        starting_player=0,
        liar=None,
        broken_shooter=None,
        invalid_fleets=False,
        broken_close=None,
        repeat=False,
        opening_miss=None,
        miss_during_series=False,
        slow_player=None,
        slow_endpoint=None,
        liar_result ='miss',
        opening_kill=False,
        shot_override=None,
        max_shots=1000

):
    fleets = [
        generate_fleet(random.Random(10)),
        generate_fleet(random.Random(20))
    ]
    sessions = [str(uuid4()), str(uuid4())]
    service_boards = [Board(fleet) for fleet in fleets]
    service_results = [{}, {}]
    requests = []

    shot_sequences = []

    for player in (0, 1):
        enemy_fleet = fleets[1 - player]

        coordinates = [coordinate for ship in enemy_fleet for coordinate in ship['coordinates']]

        occupied = set(coordinates)
        water_coordinate = next(
            f'{letter}{row}' for row in range(1, 11)
            for letter in 'ABCDEFGHIF' if f'{letter}{row}' not in occupied
        )

        if opening_kill and player == 0:
            single_coordinate = next(ship['coordinates'][0] for ship in enemy_fleet if len(ship['coordinates']) == 1)

            coordinates.remove(single_coordinate)
            coordinates.insert(0, single_coordinate)

        if player == opening_miss:
            coordinates.insert(0, water_coordinate)

        if miss_during_series:
            if player == 0:
                coordinates.insert(1, water_coordinate)
            else:
                coordinates.insert(0, water_coordinate)

        if repeat:
            coordinates.insert(1, coordinates[0])

        shot_sequences.append(iter(coordinates))

    def make_handler(player):
        async def handler(request):
            path = request.url.path
            prefix = f'/game/{sessions[player]}'

            requests.append((player, path))

            is_slow_request = (player == slow_player and (
                (slow_endpoint == 'game' and path == '/game')
                or path == f'{prefix}/{slow_endpoint}'
            ))

            if is_slow_request:
                await asyncio.sleep(0.1)

            if path =='/game':
                return httpx.Response(201, json={
                    'session_id': sessions[player],
                    'ships': ([] if invalid_fleets else fleets [player])
                })

            if path == f'{prefix}/shot':
                if player == broken_shooter:
                    return httpx.Response(500, json={'detail': 'Test failure'})

                return httpx.Response(200, json={'coordinate': (shot_override if shot_override is not None else next(shot_sequences[player]))})

            if path == f'{prefix}/opponent-shot':
                coordinate = json.loads(request.content)['coordinate']

                if coordinate in service_results[player]:
                    actual_result = service_results[player][coordinate]
                else:
                    actual_result = service_boards[player].receive_shot(coordinate)
                    service_results[player][coordinate] = actual_result

                return httpx.Response(200, json={'result': (liar_result if player == liar else actual_result)})

            if path == f'{prefix}/shot/result':
                return httpx.Response(200, json={'status': 'accepted'})

            if path == f'{prefix}/close':
                if player == broken_close:
                    return httpx.Response(500, json={'detail': 'Cannot close'})

                return httpx.Response(200, json={'status': 'closed'})

            return httpx.Response(404, json={'detail': 'Unknown endpoint'})

        return handler

    async def run():
        timeout = 0.02 if slow_player is not None else 1.0

        async with (ServiceClient('http://localhost:8000', timeout=timeout, transport=httpx.MockTransport(make_handler(0))) as first,
                    ServiceClient('http://localhost:8001', timeout=timeout, transport=httpx.MockTransport(make_handler(1))) as second):
            return await run_match(first, second, starting_player=starting_player, max_shots=max_shots)

    result = asyncio.run(run())

    return result, requests, sessions

def assert_both_sessions_closed(requests, sessions):
    assert (0, f'/game/{sessions[0]}/close') in requests
    assert (1, f'/game/{sessions[1]}/close') in requests

@pytest.mark.parametrize('starting_player', [0, 1])
def test_complete_match(starting_player):
    result, requests, sessions = play_test_match(starting_player=starting_player)

    assert result.outcome == 'victory'
    assert result.winner == starting_player
    assert len(result.shots) == 20

    assert all(shot['player'] == starting_player for shot in result.shots)
    assert all(shot['expected'] == shot['reported'] for shot in result.shots)
    assert sum(shot['expected'] == 'killed' for shot in result.shots)

    assert result.violations == {}
    assert result.close_errors == {}
    assert_both_sessions_closed(requests, sessions)

def test_false_response_causes_technical_defeat():
    result, requests, sessions = play_test_match(liar=1)

    assert result.outcome == 'technical'
    assert result.winner == 0
    assert 'False result' in result.violations[1]
    assert (0, f'/game/{sessions[0]}/shot/result') not in requests

    assert_both_sessions_closed(requests, sessions)

def test_shooter_failure_causes_technical_defeat():
    result, requests, sessions = play_test_match(broken_shooter=0)

    assert result.outcome == 'technical'
    assert result.winner == 1
    assert 0 in result.violations
    assert_both_sessions_closed(requests, sessions)

def test_two_invalid_fleets_have_no_winner():
    result, requests, sessions = play_test_match(invalid_fleets=True)

    assert result.outcome == 'double_failure'
    assert result.winner is None
    assert set(result.violations) == {0, 1}
    assert_both_sessions_closed(requests, sessions)

def test_close_failure_does_not_prevent_other_cleanup():
    result, requests, sessions = play_test_match(broken_close=0)

    assert result.outcome == 'victory'
    assert result.winner == 0
    assert 0 in result.close_errors
    assert 1 not in result.close_errors
    assert_both_sessions_closed(requests, sessions)

@pytest.mark.parametrize('first_result', ['hit', 'killed', 'miss'])
def test_repeated_shot_passes_turn_and_match_continues(first_result):
    result, requests, sessions = play_test_match(
        repeat=True,
        opening_miss=0 if first_result == 'miss' else None,
        opening_kill=first_result == 'killed'
    )

    assert result.outcome == 'victory'
    assert result.winner == (1 if first_result == 'miss' else 0)
    assert result.violations == {}
    assert len(result.shots) == 23

    repeated_shots = [shot for shot in result.shots if shot['repeated']]

    assert len(repeated_shots) == 2

    assert all(shot['expected'] == shot['reported'] for shot in result.shots)

    for index, shot in enumerate(result.shots):
        if shot['repeated']:
            assert index + 1 < len(result.shots)
            assert (result.shots[index + 1]['player'] == 1 - shot['player'])

    for player in (0, 1):
        sent_results = requests.count((player, f'/game/{sessions[player]}/shot/result'))
        player_shots = sum(shot['player'] == player for shot in result.shots)

        assert sent_results == player_shots

    assert_both_sessions_closed(requests, sessions)

def test_shot_limit_stops_match_without_technical_defeat():
    result, requests, sessions = play_test_match(max_shots=1)

    assert result.outcome == 'interrupted'
    assert result.winner is None
    assert result.reason == 'Shot limit reached'
    assert result.violations == {}
    assert len(result.shots) == 1

    assert_both_sessions_closed(requests, sessions)

@pytest.mark.parametrize('starting_player', [0, 1])
def test_miss_passes_turn_to_opponent(starting_player):
    result, requests, sessions = play_test_match(starting_player=starting_player, opening_miss=starting_player)
    opponent = 1 - starting_player

    assert result.outcome == 'victory'
    assert result.winner == opponent
    assert len(result.shots) == 21

    first_shot = result.shots[0]

    assert first_shot['player'] == starting_player
    assert first_shot['expected'] == 'miss'
    assert first_shot['reported'] == 'miss'

    assert all(shot['player'] == opponent for shot in result.shots[1:])

    result_position = requests.index((starting_player, f'/game/{sessions[starting_player]}/shot/result'))
    opponent_shot_position = requests.index((opponent, f'/game/{sessions[opponent]}/shot'))

    assert result_position < opponent_shot_position
    assert_both_sessions_closed(requests, sessions)

def test_series_resumes_after_opponent_miss():
    result, requests, sessions = play_test_match(miss_during_series=True)

    assert result.outcome == 'victory'
    assert result.winner == 0
    assert len(result.shots) == 22

    opening = [(shot['player'], shot['expected']) for shot in result.shots[:4]]

    assert opening == [
        (0, 'hit'),
        (0, 'miss'),
        (1, 'miss'),
        (0, 'hit')
    ]

    assert all(shot['player'] == 0 for shot in result.shots[3:])
    assert all(shot['expected'] == shot['reported'] for shot in result.shots)

    assert_both_sessions_closed(requests, sessions)

@pytest.mark.parametrize(
    ('slow_player', 'slow_endpoint', 'winner'), [
        (0, 'shot', 1),
        (1, 'opponent-shot', 0),
        (0, 'shot/result', 1)
    ]
)
def test_gameplay_timeout_causes_technical_defeat(slow_player, slow_endpoint, winner):
    result, requests, sessions = play_test_match(slow_player=slow_player, slow_endpoint=slow_endpoint)

    assert result.outcome == 'technical'
    assert result.winner == winner
    assert 'timeout' in result.violations[slow_player]

    assert_both_sessions_closed(requests, sessions)

def test_start_timeout_closes_other_know_session():
    result, requests, sessions = play_test_match(slow_player=0, slow_endpoint='game')

    assert result.outcome == 'technical'
    assert result.winner == 1
    assert 'timeout' in result.violations[0]

    assert(0, f'/game/{sessions[0]}/close') not in requests
    assert (1, f'/game/{sessions[1]}/close') in requests

def test_close_timeout_does_not_block_other_cleanup():
    result, requests, sessions = play_test_match(slow_player=0, slow_endpoint='close')

    assert result.outcome == 'victory'
    assert result.winner == 0
    assert 'timeout' in result.close_errors[0]
    assert 1 not in result.close_errors

    assert_both_sessions_closed(requests, sessions)

@pytest.mark.parametrize(
    ('expected', 'reported'),
    [
        ('miss', 'hit'),
        ('miss', 'killed'),
        ('hit', 'miss'),
        ('hit', 'killed'),
        ('killed', 'miss'),
        ('killed', 'hit')
    ]
)
def test_every_false_result_causes_technical_defeat(expected, reported):
    result, requests, sessions = play_test_match(
        liar=1,
        liar_result=reported,
        opening_miss=0 if expected == 'miss' else None,
        opening_kill=expected == 'killed'
    )

    assert result.outcome == 'technical'
    assert result.winner == 0
    assert 'False result' in result.violations[1]

    assert len(result.shots) == 1
    assert result.shots[0]['expected'] == expected
    assert result.shots[0]['reported'] == reported

    assert (0, f'/game/{sessions[0]}/shot/result') not in requests

    assert_both_sessions_closed(requests, sessions)

@pytest.mark.parametrize('coordinate', ['K1', 'A0'])
def test_invalid_coordinate_causes_shooter_defeat(coordinate):
    result, requests, sessions = play_test_match(shot_override=coordinate)

    assert result.outcome == 'technical'
    assert result.winner == 1
    assert 'Invalid shot coordinate' in result.violations[0]
    assert result.shots == []
    assert (1, f'/game/{sessions[1]}/opponent-shot') not in requests

    assert_both_sessions_closed(requests, sessions)