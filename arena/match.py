from dataclasses import dataclass, field
from random import randrange

from arena.board import Board
from arena.client import ServiceClient, ServiceError


@dataclass
class MatchResult:
    starting_player: int
    winner: int | None = None
    outcome: str = 'interrupted'
    reason: str = ''

    shots: list[dict] = field(default_factory=list)
    violations: dict[int, str] = field(default_factory=dict)
    close_errors: dict[int, str] = field(default_factory=dict)


async def run_match(
    first_client: ServiceClient,
    second_client: ServiceClient,
    *,
    starting_player: int | None = None,
    max_shots: int = 1000
) -> MatchResult:
    if starting_player is None:
        starting_player = randrange(2)

    if starting_player not in (0, 1):
        raise ValueError('Starting player must be 0 or 1')

    if (not isinstance(max_shots, int) or isinstance(max_shots, bool)  or max_shots < 1):
        raise ValueError('Shot limit must be a positive integer')

    if first_client is second_client:
        raise ValueError('Use a separate client for each participant')

    clients = (first_client, second_client)
    boards: list[Board | None] = [None, None]

    previous_results: list[dict[str, str]] = [{}, {}]

    result = MatchResult(starting_player=starting_player)

    def technical_defeat(player: int, reason: str) -> None:
        result.winner = 1 - player
        result.outcome = 'technical'
        result.reason = reason
        result.violations[player] = reason

    try:
        for player, client in enumerate(clients):
            try:
                game = await client.start_game()
                boards[player] = Board(game['ships'])
            except ServiceError as exc:
                result.violations[player] = str(exc)

        if len(result.violations) == 2:
            result.outcome = 'double_failure'
            result.reason = 'Both participants failed to start'
            return result

        if result.violations:
            failed_player = next(iter(result.violations))

            technical_defeat(failed_player, result.violations[failed_player])
            return result

        if (first_client.base_url == second_client.base_url and first_client.created_session_id == second_client.created_session_id):
            result.reason = 'Participants received the same session'
            return result

        current_player = starting_player

        for _ in range(max_shots):
            opponent = 1 - current_player

            attacker = clients[current_player]
            defender = clients[opponent]

            attacker_session = attacker.created_session_id
            defender_session = defender.created_session_id
            defender_board = boards[opponent]

            try:
                coordinate = await attacker.make_shot(attacker_session)
            except ServiceError as exc:
                technical_defeat(current_player, str(exc))
                return result

            history = previous_results[current_player]
            repeated = coordinate in history

            if repeated:
                expected_result = history[coordinate]
            else:
                expected_result = defender_board.receive_shot(coordinate)
                history[coordinate] = expected_result

            shot = {
                'player': current_player,
                'coordinate': coordinate,
                'expected': expected_result,
                'reported': None,
                'repeated': repeated
            }
            result.shots.append(shot)

            try:
                reported_result = await defender.opponent_shot(defender_session, coordinate)
            except ServiceError as exc:
                technical_defeat(opponent, str(exc))
                return result

            shot['reported'] = reported_result

            if reported_result != expected_result:
                technical_defeat(
                    opponent,
                    f'False result for {coordinate}: '
                    f'expected {expected_result}, '
                    f'got {reported_result}'
                )
                return result

            try:
                await attacker.report_result(attacker_session, expected_result)
            except ServiceError as exc:
                technical_defeat(current_player, str(exc))
                return result

            if not repeated and defender_board.is_defeated:
                result.winner = current_player
                result.outcome = 'victory'
                result.reason = 'Opponent fleet destroyed'
                return result

            if repeated or expected_result == 'miss':
                current_player = opponent

        result.reason = 'Shot limit reached'
        return result

    finally:
        closed_sessions = set()

        for player, client in enumerate(clients):
            session_id = client.created_session_id

            if session_id is None:
                continue

            session_key = (client.base_url, session_id)

            if session_key in closed_sessions:
                continue

            closed_sessions.add(session_key)

            try:
                await client.close_game(session_id)
            except ServiceError as exc:
                result.close_errors[player] = str(exc)