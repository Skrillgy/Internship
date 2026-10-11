from app.fleet import parse_coordinate, validate_fleet

class RepeatedShotError(ValueError):
    """Повторный выстрел в уже проверенную клетку."""

class Board:
    """Контрольное поле, пренадлежащее арене."""

    def __init__(self, ships: list[dict[str, list[str]]]):
        if not validate_fleet(ships):
            raise ValueError('Invalid fleet')

        self._ships = tuple(frozenset(ship['coordinates']) for ship in ships)
        self._occupied = frozenset(coordinate for ship in self._ships for coordinate in ship)

        self._shots: set[str] = set()
        self._hits: set[str] = set()

    @property
    def remaining_decks(self) -> int:
        return len(self._occupied - self._hits)

    @property
    def is_defeated(self) -> bool:
        return self.remaining_decks == 0

    def receive_shot(self, coordinate: str) -> str:
        parse_coordinate(coordinate)

        if coordinate in self._shots:
            raise RepeatedShotError(f'Repeated shot: {coordinate}')

        self._shots.add(coordinate)

        if coordinate not in self._occupied:
            return 'miss'

        self._hits.add(coordinate)

        ship = next(ship for ship in self._ships if coordinate in ship)

        if ship <= self._hits:
            return 'killed'

        return 'hit'