from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import SessionLocal, engine
from app.fleet import generate_fleet
from app.main import app
from app.models import Game

client = TestClient(app)

EXPECTED_SHIP_LENGTHS = [1, 1, 1, 1, 2, 2, 2, 3, 3, 4]

def parse_coordinate(coordinate: str) -> tuple[int, int]:
    assert len(coordinate) >= 2

    column_letter = coordinate[0]
    row_text = coordinate[1:]

    assert column_letter in 'ABCDEFGHIJ'

    assert row_text.isdigit()
    row_number = int(row_text)

    assert 1 <= row_number <= 10
    column = ord(column_letter) - ord('A')
    row = row_number - 1

    return row, column

def assert_ship_is_straight_and_contiguous(
    coordinates: list[str],
) -> None:
    cells = [
        parse_coordinate(coordinate)
        for coordinate in coordinates
    ]

    if len(cells) == 1:
        return

    rows = {row for row, _ in cells}
    columns = {column for _, column in cells}

    assert len(rows) == 1 or len(columns) == 1

    if len(rows) == 1:
        positions = sorted(
            column
            for _, column in cells
        )
    else:
        positions = sorted(
            row
            for row, _ in cells
        )

    expected_positions = list(
        range(
            positions[0],
            positions[0] + len(positions)
        )
    )

    assert positions == expected_positions

def assert_ships_do_not_touch(
    ships: list[dict[str, list[str]]]
) -> None:
    ship_cells = [
        {
            parse_coordinate(coordinate)
            for coordinate in ship['coordinates']
        }
        for ship in ships
    ]

    for first_index in range(len(ship_cells)):
        for second_index in range(
            first_index + 1,
            len(ship_cells)
        ):
            first_ship = ship_cells[first_index]
            second_ship = ship_cells[second_index]

            for first_row, first_column in first_ship:
                for second_row, second_column in second_ship:
                    row_distance = abs(
                        first_row - second_row
                    )
                    column_distance = abs(
                        first_column - second_column
                    )

                    assert not (
                        row_distance <= 1
                        and column_distance <= 1
                    )

def assert_fleet_is_valid(
    ships: list[dict[str, list[str]]]
) -> None:
    assert len(ships) == 10

    ship_lengths = sorted(
        len(ship['coordinates'])
        for ship in ships
    )

    assert ship_lengths ==   EXPECTED_SHIP_LENGTHS

    all_coordinates = [
        coordinate
        for ship in ships
        for coordinate in ship['coordinates']
    ]

    assert len(all_coordinates) == 20

    assert len(set(all_coordinates)) == 20

    for ship in ships:
        assert_ship_is_straight_and_contiguous(
            ship['coordinates']
        ) 

    assert_ships_do_not_touch(ships)     

def test_games_table_exists():
    inspector = inspect(engine)

    assert inspector.has_table('games')

def test_generated_fleet_is_valid():
    for _ in range(50):
        fleet = generate_fleet()
        assert_fleet_is_valid(fleet)

def test_start_game():
    response = client.post('/games')

    assert response.status_code == 200

    body = response.json()

    assert "session_id" in body
    assert "ships" in body

    session_id = UUID(body['session_id'])
    ships = body['ships']
    assert_fleet_is_valid(ships)

    with SessionLocal() as db:
        game = db.get(Game, session_id)

        assert game is not None
        assert game.status == 'active'
        assert game.ships == ships

        db.delete(game)
        db.commit()