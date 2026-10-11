import argparse
import asyncio
from urllib.parse import urlsplit

from arena.client import ServiceClient
from arena.match import MatchResult, run_match
from arena.config import load_participants
from arena.tournament import TournamentResult, run_tournament
from arena.report import save_tournament_report

def parse_service_url(value: str) -> str:
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Некорректный адрес сервиса') from exc

    if url.scheme not in {'http', 'https'}:
        raise argparse.ArgumentTypeError('Адрес должен начинатся с http:// или https://')

    if url.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise argparse.ArgumentTypeError('Для этой арены укажи локальный адрес сервиса')

    if port is None or not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError('Укажи порт сервиса от 1 до 65535')

    if (
        url.username is not None
        or url.password is not None
        or url.path not in {'', '/'}
        or url.query
        or url.fragment
    ):
        raise argparse.ArgumentTypeError('Нужен адрес вида http://localhost:8000')

    return value.rstrip('/')

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Арена для REST-сервисов морского боя')
    commands = parser.add_subparsers(dest='command', required=True)

    match_parser = commands.add_parser('match', help='Провести один матч')
    match_parser.add_argument('--first', required=True, type=parse_service_url)
    match_parser.add_argument('--second', required=True, type=parse_service_url)
    match_parser.add_argument('--first-name', default='Игрок 1')
    match_parser.add_argument('--second-name', default='Игрок 2')
    match_parser.add_argument(
        '--starting-player',
        type=int,
        choices=(0, 1),
        default=None,
        help='Кто начинает: 0 или 1; по умолчанию жеребьёвка'
    )

    tournament_parser = commands.add_parser('tournament', help='Провести турнир каждый с каждым')
    tournament_parser.add_argument(
        '--players',
        required=True,
        help='Путь к JSON-файлу участников'
    )
    tournament_parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Начальное значение для жеребьёвки первых ходов'
    )
    tournament_parser.add_argument(
        '--allow-shared-service',
        action='store_true',
        help='Разрешить один сеанс для нескольких тестовых учасников'
    )
    tournament_parser.add_argument(
        '--report',
        default=None,
        help='Путь для сохранения JSON-отчёта турнира'
    )

    return parser

def print_match_result(
        result: MatchResult,
        names: tuple[str, str]
) -> None:
    print(f'\nПервый ход: {names[result.starting_player]}')

    print('\nХоды:')

    for number, shot in enumerate(result.shots, start=1):
        player_name = names[shot['player']]
        reported = shot['reported']

        if reported is None:
            reported = 'ответ не получен'

        print(
            f'{number:3}. {player_name}: '
            f'{shot["coordinate"]} - '
            f'ожидалось {shot["expected"]}, '
            f'получено {reported}'
        )

    outcomes = {
        'victory': 'Победа по уничтожению флота',
        'technical': 'Техническое победа',
        'double_failure': 'Ошибка обоих участников',
        'interrupted': 'Матч остановлен'
    }

    print(f'\nИтог: {outcomes.get(result.outcome, result.outcome)}')

    if result.winner is None:
        print('Победитель не определён')
    else:
        print(f'Победитель: {names[result.winner]}')

    print(f'Причина: {result.reason}')
    print(f'Проверено выстрелов: {len(result.shots)}')

    for player, error in result.violations.items():
        print(f'Нарушение - {names[player]}: {error}')

    if result.close_errors:
        for player, error in result.close_errors.items():
            print(f'Ошибка закрытия - {names[player]}: {error}')
    else:
        print('Закрытие известных сессий: без ошибок')

async def play(args) -> MatchResult:
    async with (ServiceClient(args.first) as first, ServiceClient(args.second) as second):
        return await run_match(first, second, starting_player=args.starting_player)

def print_tournament_result(result: TournamentResult) -> None:
    outcomes = {
        'victory': 'потопление флота',
        'technical': 'техническая победа',
        'double_failure': 'ошибка обоих участников',
        'interrupted': 'матч остановлен'
    }

    print('\nРезультаты матчейЖ')

    for number, math in enumerate(result.matches, start=1):
        names = (math.first.name, math.second.name)
        game = math.result

        winner = (names[game.winner] if game.winner is not None else 'не определён')

        print(f'\n{number}. {names[0]} против {names[1]}')
        print(f'   Первый ход: {names[game.starting_player]}')
        print(
            f'   Победитель: {winner}; '
            f'{outcomes.get(game.outcome, game.outcome)}'
        )
        print(f'   Проверено выстрелов: {len(game.shots)}')
        print(f'   Причина: {game.reason}')

        for player, error in game.violations.items():
            print(f'   Нарушение — {names[player]}: {error}')

        for player, error in game.close_errors.items():
            print(f'   Ошибка закрытия — {names[player]}: {error}')

    print('\nИтоговая таблица:')

    name_width = max(12, max(len(standing.participant.name) for standing in result.standings))

    print(
        f'{"Место":>5} '
        f'{"Участник":<{name_width}} '
        f'{"Игр":>4} '
        f'{"Побед":>6} '
        f'{"Пораж.":>6} '
        f'{"Без итога":>9} '
        f'{"Очков":>6}'
    )

    for standing in result.standings:
        print(
            f'{standing.rank:>5} '
            f'{standing.participant.name:<{name_width}} '
            f'{standing.played:>4} '
            f'{standing.wins:>6} '
            f'{standing.losses:>6} '
            f'{standing.unresolved:>9} '
            f'{standing.points:>6}'
        )

    unresolved_matches = sum(match.result.winner is None for match in result.matches)

    print(f'\nПроведено матчей: {len(result.matches)}')

    if unresolved_matches:
        print(f'Матчей без победителя: {unresolved_matches}')
        print('Итоговый победитель турнира пока не определён')
        return

    best_points = result.standings[0].points
    leaders = [standing.participant.name for standing in result.standings if standing.points == best_points]

    if len(leaders) == 1:
        print(f'Победитель турнира: {leaders[0]}')
    else:
        print(f'Первое место делят: {", ".join(leaders)}')

async def play_tournament(args) -> TournamentResult:
    participants = load_participants(args.players)

    math_count = len(participants) * (len(participants) - 1) // 2

    print(f'Участников: {len(participants)}', flush=True)
    print(f'Запланировано матчей: {math_count}', flush=True)
    print('Максимальное время ответа: 1 секунда', flush=True)
    print('Турнир выполняется...', flush=True)

    return await run_tournament(
        participants,
        seed=args.seed,
        allow_shared_service=args.allow_shared_service
    )

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == 'match':
            names = (args.first_name, args.second_name)

            print(f'Матч: {names[0]} против {names[1]}', flush=True)
            print(f'{names[0]}: {args.first}', flush=True)
            print(f'{names[1]}: {args.second}', flush=True)
            print('Максимальное время ответа: 1 секунда', flush=True)
            print('Матч выполняется...', flush=True)

            result = asyncio.run(play(args))

            print_match_result(result, names)

            if (result.outcome in {'victory', 'techical'} and not result.close_errors):
                return 0

            return 1

        result = asyncio.run(play_tournament(args))
        print_tournament_result(result)

        if args.report is not None:
            report_path = save_tournament_report(result, args.report)
            print(f'\nОтчёт сохранён: {report_path}')

        has_problems = any(match.result.winner is None or bool(match.result.close_errors) for match in result.matches)

        return 1 if has_problems else 0

    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    except KeyboardInterrupt:
        print('\nЗапуск прерван пользователем')
        return 130

if __name__ == '__main__':
    raise SystemExit(main())