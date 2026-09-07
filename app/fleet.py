import random

BOARD_SIZE =10

# Флот морского боя
SHIP_LENGTHS = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]

def to_coordinate(row: int, column: int) -> str:
    letter = chr(ord('A') + column)
    return f'{letter}{row + 1}'

def generate_fleet() -> list[dict[str, list[str]]]:
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

def can_place_ship(
    cells: list[tuple[int, int]],
    occupied: set[tuple[int, int]]
) -> bool:
    for row, column in cells:
        for row_offset in (-1, 0, 1):
            for column_offset in (-1, 0, 1):
                neighbour = (
                    row + row_offset,
                    column + column_offset
                )

                if neighbour in occupied:
                    return False
    return True