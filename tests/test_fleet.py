from copy import deepcopy
import random
import pytest

from app.fleet import (
    SHIP_LENGTHS,
    can_place_ship,
    generate_fleet,
    parse_coordinate,
    validate_fleet
)

VALID_FLEET = [
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

@pytest.fixture
def valid_fleet():
    return deepcopy(VALID_FLEET)

def test_know_valid_fleet_is_accepted():
    assert validate_fleet(VALID_FLEET)

def test_diagonal_ship_is_rejected(valid_fleet):
    valid_fleet[4]['coordinates'] = ['D4', 'E5']

    assert not validate_fleet(valid_fleet)

def test_ship_with_gap_is_rejected(valid_fleet):
    valid_fleet[4]['coordinates'] = ['D4', 'F4']

    assert not validate_fleet(valid_fleet)

def test_ships_touching_by_side_are_rejected(valid_fleet):
    valid_fleet[6]['coordinates'] = ['H6']

    assert not validate_fleet(valid_fleet)

def test_ships_touching_by_corner_are_rejected(valid_fleet):
    valid_fleet[6]['coordinates'] = ['G6']

    assert not validate_fleet(valid_fleet)

def test_overlapping_ships_are_rejected(valid_fleet):
    valid_fleet[6]['coordinates'] = ['H5']

    assert not validate_fleet(valid_fleet)

def test_coordinate_outside_board_is_rejected(valid_fleet):
    valid_fleet[9]['coordinates'] = ['K10']

    assert not validate_fleet(valid_fleet)

def test_wrong_ship_count_is_rejected(valid_fleet):
    valid_fleet.pop()

    assert not validate_fleet(valid_fleet)

def test_wrong_ship_lengths_are_rejected(valid_fleet):
    valid_fleet[1]['coordinates'] = ['F1', 'G1', 'H1', 'I1']

    assert not validate_fleet(valid_fleet)

def test_generated_fleet_is_valid():
    for seed in range(100):
        rng = random.Random(seed)
        fleet = generate_fleet(rng)

        assert validate_fleet(fleet)
        
def test_generated_fleet_has_correct_ship_count():
    fleet = generate_fleet(random.Random(1))

    assert len(fleet) == 10

def test_generated_fleet_has_correct_ship_lengths():
    fleet = generate_fleet(random.Random(2))

    ship_lengths = sorted(
        len(ship["coordinates"])
        for ship in fleet
    )

    assert ship_lengths == sorted(SHIP_LENGTHS)


def test_generated_fleet_has_twenty_decks():
    fleet = generate_fleet(random.Random(3))

    deck_count = sum(
        len(ship["coordinates"])
        for ship in fleet
    )

    assert deck_count == 20

@pytest.mark.parametrize(
    'coordinate', ['A1', 'A10', 'J1', 'J10', 'D7']
)

def test_valid_coordinates_are_accepted(coordinate):
    row, column = parse_coordinate(coordinate)

    assert 0 <= row < 10
    assert 0 <= column < 10

@pytest.mark.parametrize(
    'coordinate', ['A0', 'A11', 'K1', 'a1', 'A01', 'AA1', '1A', '']
)

def test_invalid_coordinates_are_rejected(coordinate):
    with pytest.raises(ValueError):
        parse_coordinate(coordinate)

def test_can_place_ship_on_empty_board():
    cells = [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3)
    ]

    assert can_place_ship(cells, set())

def test_can_place_ship_rejects_overlap():
    occupied = {(5, 5)}
    cells = [
        (5, 5),
        (5, 6)
    ]

    assert not can_place_ship(cells, occupied)

def test_can_place_ship_rejects_side_touch():
    occupied = {(5, 5)}
    cells = [(5, 6)]

    assert not can_place_ship(cells, occupied)

def test_can_plase_ship_rejects_corner_touch():
    occupied = {(5, 5)}
    cells = [(6, 6)]

    assert not can_place_ship(cells, occupied)

def test_can_place_ship_allows_safe_destance():
    occupied = {(5, 5)}
    cells = [(7, 7)]

    assert can_place_ship(cells, occupied)

def test_can_place_ship_rejects_negative_row():
    cells = [(-1, 0)]

    assert not can_place_ship(cells, set())

def test_can_plase_ship_rejects_negative_column():
    cells = [(0, -1)]

    assert not can_place_ship(cells, set())

def test_can_place_ship_rejects_row_outside_board():
    cells = [(10, 0)]

    assert not can_place_ship(cells, set())

def test_can_place_ship_rejects_column_outside_board():
    cells = [(0, 10)]

    assert not can_place_ship(cells, set())

def test_none_fleet_is_rejected():
    assert not validate_fleet(None)

def test_fleet_must_be_a_list():
    assert not validate_fleet({'ships': []})

def test_ship_must_be_a_ditionary(valid_fleet):
    valid_fleet[0] = 'A1'

    assert not validate_fleet(valid_fleet)

def test_ship_must_have_coordinates(valid_fleet):
    valid_fleet[0] = {}

    assert not validate_fleet(valid_fleet)

def test_coordinates_must_be_a_list(valid_fleet):
    valid_fleet[0]['coordinates'] = 'A1'

    assert not validate_fleet(valid_fleet)

def test_coordinate_must_be_a_string(valid_fleet):
    valid_fleet[0]['coordinates'] = ['A1', 'B1', 'C1', 123]

    assert not validate_fleet(valid_fleet)

def test_unhashable_coordinate_is_rejected(valid_fleet):
    valid_fleet[0]['coordinates'] = ['A1', 'B1', 'C1', ['D1']]

    assert not validate_fleet(valid_fleet)

def test_generate_fleet_is_reproducible_with_same_seed():
    first_fleet = generate_fleet(random.Random(42))
    second_fleet = generate_fleet(random.Random(42))

    assert first_fleet == second_fleet