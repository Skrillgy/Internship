from app.fleet import parse_coordinate

def resolve_opponent_shot(
        ships: list[dict[str, list[str]]],
        opponent_shots: dict[str, str],
        coordinate: str
) -> str:
    parse_coordinate(coordinate)

    if coordinate in opponent_shots:
        return opponent_shots[coordinate]

    hit_cells = {
        shot_coordinate
        for shot_coordinate, result in opponent_shots.items()
        if result in {'hit', 'killed'}
    }

    for ship in ships:
        ship_coordinates = ship['coordinates']

        if coordinate not in ship_coordinates:
            continue

        ship_is_killed = all(
            cell == coordinate or cell in hit_cells
            for cell in ship_coordinates
        )

        if ship_is_killed:
            return 'killed'

        return 'hit'

    return 'miss'

def _is_available(
        row: int,
        column:int,
        own_shots: dict[str,str]
) -> bool:
    if not (0 <= row < 10 and 0 <= column < 10):
        return False

    coordinate = (f"{chr(ord('A') + column)}{row + 1}")
    return coordinate not in own_shots

def _to_coordinate(row: int, column: int) -> str:
    return f"{chr(ord('A') + column)}{row + 1}"

def choose_shot(
        own_shots: dict[str, str],
        target_hits: list[str]
) -> str:
    if target_hits:
        hit_cells = [
            parse_coordinate(coordinate)
            for coordinate in target_hits
        ]

        if len(hit_cells) >= 2:
            rows = {
                row
                for row, _ in hit_cells
            }
            columns = {
                column
                for _, column in hit_cells
            }

            if len(rows) == 1:
                row = hit_cells[0][0]

                hit_columns = sorted(
                    column
                    for _, column in hit_cells
                )

                candidates = [
                    (row, hit_columns[0] - 1),
                    (row, hit_columns[-1] + 1)
                ]

                for candidate_row, candidate_column in candidates:
                    if _is_available(candidate_row, candidate_column, own_shots):
                        return _to_coordinate(candidate_row, candidate_column)

            if len(columns) == 1:
                column = hit_cells[0][1]

                hit_rows = sorted(
                    row
                    for row, _ in hit_cells
                )

                candidates = [
                    (hit_rows[0] - 1, column),
                    (hit_rows[-1] + 1, column)
                ]

                for candidate_row, candidate_column in candidates:
                    if _is_available(candidate_row, candidate_column, own_shots):
                        return _to_coordinate(candidate_row, candidate_column)

        else:
            row, column = hit_cells[0]

            candidates = [
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1)
            ]

            for candidate_row, candidate_column in candidates:
                if _is_available(candidate_row, candidate_column, own_shots):
                    return _to_coordinate(candidate_row, candidate_column)

    for row in range(10):
        for column in range(10):
            if (
                (row + column) % 2 == 0
                and _is_available(row, column, own_shots)
            ):
                return _to_coordinate(row, column)

    for row in range(10):
        for column in range(10):
            if _is_available(row, column, own_shots):
                return _to_coordinate(row,column)

    raise RuntimeError('No available shots')