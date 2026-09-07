import random
import re

BOARD_SIZE = 10

# Флот морского боя
SHIP_LENGTHS = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]

COORDINATE_PATTERN = re.compile(r"^[A-J](?:[1-9]|10)$")

def to_coordinate(row: int, column: int) -> str:
    letter = chr(ord('A') + column)
    return f'{letter}{row + 1}'

def parse_coordinate(coordinate: str) -> tuple[int, int]:
    if not isinstance(coordinate, str):
        raise ValueError('Coordinate must be a string')

    if COORDINATE_PATTERN.fullmatch(coordinate) is None:
        raise ValueError(f'Invalid coordinate: {coordinate}')

    column_letter = coordinate[0]
    row_number = int(coordinate[1:])

    column = ord(column_letter) - ord('A')
    row = row_number - 1

    return row, column

def is_ship_straight_and_contiguous(
    coordinates: list[str]
) -> bool:
    if not coordinates:
        return False

    try:
        cells = [
            parse_coordinate(coordinate)
            for coordinate in coordinates
        ]
    except ValueError:
        return False

    if len(set(cells)) != len(cells):
        return False

    if len(cells) == 1:
        return True

    rows = {row for row, _ in cells}
    columns = {column for _, column in cells}

    if len(rows) == 1:
        positions = sorted(
            column
            for _, column in cells
        )
    elif len(columns) == 1:
        positions = sorted(
            row
            for row, _ in cells
        )
    else:
        return False

    expected_positions = list(
        range(
            positions[0],
            positions[0] + len(positions)
        )
    )

    return positions == expected_positions

def ships_do_not_touch(
    ships: list[dict[str, list[str]]]
) -> bool:
    ship_cells = []

    try:
        for ship in ships:
            coordinates = ship['coordinates']
            cells = {
                parse_coordinate(coordinate)
                for coordinate in coordinates
            }

            ship_cells.append(cells)

    except (KeyError, TypeError, ValueError):
        return False

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

                if (
                    row_distance <= 1
                    and column_distance <= 1
                ):
                    return False
    return True

def validate_fleet(ships: object) -> bool:
    if not isinstance(ships, list):
        return False

    if len(ships) != 10:
        return False

    for ship in ships:
        if not isinstance(ship, dict):
            return False

        coordinates = ship.get('coordinates')

        if not isinstance(coordinates, list):
            return False

        if not all(
            isinstance(coordinate, str)
            for coordinate in coordinates
        ):
            return False

    ship_lengths = sorted(
        len(ship['coordinates'])
        for ship in ships
    )

    if ship_lengths != sorted(SHIP_LENGTHS):
        return False

    all_coordinates = [
        coordinate
        for ship in ships
        for coordinate in ship['coordinates']
    ]

    if len(all_coordinates) != 20:
        return False

    if len(set(all_coordinates)) != 20:
        return False

    for ship in ships:
        if not is_ship_straight_and_contiguous(
            ship['coordinates']
        ):
            return False

    if not ships_do_not_touch(ships):
        return False

    return True

def can_place_ship(
    cells: list[tuple[int, int]],
    occupied: set[tuple[int, int]]
) -> bool:
    for row, column in cells:
        if not (
            0 <= row < BOARD_SIZE
            and 0 <= column < BOARD_SIZE
        ):
            return False

        for row_offset in (-1, 0, 1):
            for column_offset in (-1, 0, 1):
                neighbour = (
                    row + row_offset,
                    column + column_offset
                )

                if neighbour in occupied:
                    return False
    return True

def generate_fleet(
    rng: random.Random | None = None
) -> list[dict[str, list[str]]]:
    random_source = rng if rng is not None else random

    while True:
        occupied: set[tuple[int, int]] = set()
        fleet: list[dict[str, list[str]]] = []

        success = True

        for length in SHIP_LENGTHS:
            ship_placed = False

            for _ in range(1000):
                horizontal = random.choice([True, False])

                if horizontal:
                    row = random.randrange(BOARD_SIZE)
                    column = random.randrange(BOARD_SIZE - length + 1)

                    cells = [
                        (row, column + offset)
                        for offset in range(length)
                    ]

                else:
                    row = random.randrange(BOARD_SIZE - length + 1)
                    column = random.randrange(BOARD_SIZE)

                    cells = [
                        (row + offset, column)
                        for offset in range(length)
                    ]

                if can_place_ship(cells, occupied):
                    occupied.update(cells)
                    fleet.append(
                        {
                            'coordinates': [
                                to_coordinate(row, column)
                                for row, column in cells
                            ]
                        }
                    )

                    ship_placed = True
                    break

            if not ship_placed:
                success = False
                break

        if success:
            return fleet