from copy import deepcopy

import pytest

from arena.board import Board, RepeatedShotError

@pytest.fixture
def fleet():
    return [
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

def test_miss_does_not_reduce_remaining_decks(fleet):
    board = Board(fleet)

    assert board.receive_shot('B3') == 'miss'
    assert board.remaining_decks == 20
    assert not board.is_defeated

def test_ship_is_killed_only_after_last_deck(fleet):
    board = Board(fleet)

    assert board.receive_shot('C1') == 'hit'
    assert board.receive_shot('A1') == 'hit'
    assert board.receive_shot('D1') == 'hit'
    assert board.receive_shot('B1') == 'killed'
    assert board.remaining_decks == 16

def test_single_deck_ship_is_killed_immediately(fleet):
    board = Board(fleet)

    assert board.receive_shot('J10') == 'killed'
    assert board.remaining_decks == 19

@pytest.mark.parametrize('coordinate', ['A1', 'B3', 'J10'])
def test_repeated_shot_does_not_change_state(fleet, coordinate):
    board = Board(fleet)
    board.receive_shot(coordinate)
    remaining_decks = board.remaining_decks

    with pytest.raises(RepeatedShotError):
        board.receive_shot(coordinate)

    assert board.remaining_decks == remaining_decks

@pytest.mark.parametrize('coordinate', ['A0', 'K1', 'a1', 'A11'])
def test_invalid_coordinate_does_not_change_state(fleet, coordinate):
    board = Board(fleet)

    with pytest.raises(ValueError):
        board.receive_shot(coordinate)

    assert board.remaining_decks == 20
    assert board.receive_shot('A1') == 'hit'

def test_complete_fleet_destruction(fleet):
    board = Board(fleet)

    for ship in fleet:
        coordinates = ship['coordinates']

        for index, coordinate in enumerate(coordinates):
            expected = ('killed' if index == len(coordinates) - 1 else 'hit')
            assert board.receive_shot(coordinate) == expected

    assert board.remaining_decks == 0
    assert board.is_defeated

def test_boards_have_independent_state(fleet):
    first_board = Board(fleet)
    second_board = Board(fleet)

    first_board.receive_shot('J10')

    assert first_board.remaining_decks == 19
    assert second_board.remaining_decks == 20
    assert second_board.receive_shot('J10') == 'killed'

def test_board_keeps_independent_copy_of_fleet(fleet):
    original_fleet = deepcopy(fleet)
    board = Board(fleet)

    fleet[0]['coordinates'].clear()
    fleet.clear()

    assert board.receive_shot(original_fleet[0]['coordinates'][0]) == 'hit'
    assert board.remaining_decks == 19

def test_invalid_fleet_is_rejected(fleet):
    fleet[0]['coordinates'] = ['A1', 'B1', 'C1', 'K1']

    with pytest.raises(ValueError, match='Invalid fleet'):
        Board(fleet)