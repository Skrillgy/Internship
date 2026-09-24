import pytest

from app.shots import (choose_shot, resolve_opponent_shot)

TEST_FLEET = [
    {'coordinates': ['A1', 'B1', 'C1', 'D1']},
    {'coordinates': ['F1', 'G1', 'H1']},
    {'coordinates': ['J1', 'J2', 'J3']},
    {'coordinates': ['A4', 'A5']},
    {'coordinates': ['D4', 'E4']},
    {'coordinates': ['H5', 'I5']},
    {'coordinates': ['B8']},
    {'coordinates': ['E8']},
    {'coordinates': ['H8']},
    {'coordinates': ['J10']}
]

def test_opponent_shot_miss():
    result = resolve_opponent_shot(TEST_FLEET, {}, 'C10')
    assert result == 'miss'

def test_opponent_shot_hit():
    result = resolve_opponent_shot(TEST_FLEET, {}, 'A1')
    assert result == 'hit'

def test_opponent_shot_killed_on_last_deck():
    previous_shots = {
        'A1': 'hit',
        'B1': 'hit',
        'C1': 'hit'
    }

    result = resolve_opponent_shot(TEST_FLEET, previous_shots, 'D1')
    assert result == 'killed'

def test_single_deck_ship_is_killed_immediately():
    result = resolve_opponent_shot(TEST_FLEET, {}, 'B8')
    assert result == 'killed'

def test_repeated_opponent_shot_returns_same_result():
    previous_shots = {
        'A1': 'hit'
    }

    result = resolve_opponent_shot(TEST_FLEET, previous_shots, 'A1')
    assert result == 'hit'

def test_invalid_opponent_coordinate_is_rejected():
    with pytest.raises(ValueError):
        resolve_opponent_shot(TEST_FLEET, {}, 'K1')

def test_choose_shot_returns_available_coordinate():
    coordinate = choose_shot({}, [])
    assert coordinate == 'A1'

def test_choose_shot_does_not_repeat_previous_shot():
    own_shots = {'A1': 'miss'}

    coordinate = choose_shot(own_shots, [])

    assert coordinate != 'A1'
    assert coordinate not in own_shots

def test_choose_shot_targets_neighbour_after_hit():
    own_shots = {'E5': 'hit'}

    coordinate = choose_shot(own_shots, ['E5'])

    assert coordinate in {'E4', 'E6', 'D5', 'F5'}

def test_choose_shot_continues_vertical_ship():
    own_shots = {
        'E5': 'hit',
        'E6': 'hit'
    }

    coordinate = choose_shot(own_shots, ['E5', 'E6'])

    assert coordinate in {'E4', 'E7'}

def test_choose_shot_continues_horizontal_ship():
    own_shots = {
        'E5': 'hit',
        'F5': 'hit'
    }

    coordinate = choose_shot(own_shots, ['E5', 'F5'])

    assert coordinate in {'D5', 'G5'}

def test_choose_shot_skips_known_miss_while_finishing_ship():
    own_shots = {
        'E5': 'hit',
        'E4': 'miss'
    }

    coordinate = choose_shot(own_shots, ['E5'])

    assert coordinate != 'E4'
    assert coordinate not in own_shots

def test_choose_shot_never_repeats_shots():
    own_shots = {}
    coordinates = []

    for _ in range(100):
        coordinate = choose_shot(own_shots, [])

        assert coordinate not in coordinates

        coordinates.append(coordinate)
        own_shots[coordinate] = 'miss'

    assert len(coordinates) == 100
    assert len(set(coordinates)) == 100

def test_ship_is_not_killed_before_last_deck():
    previous_shots = {
        'A1': 'hit',
        'B1': 'hit'
    }

    result = resolve_opponent_shot(TEST_FLEET, previous_shots, 'C1')

    assert result == 'hit'