import argparse

import pytest

from arena.__main__ import parse_service_url, print_match_result
from arena.match import MatchResult
from arena.__main__ import build_parser, print_tournament_result
from arena.tournament import (
    Participant,
    Standing,
    TournamentMatch,
    TournamentResult
)

@pytest.mark.parametrize('url', [
    'http://localhost:8000',
    'http://localhost:8001',
    'http://[::1]:8002'
])
def test_local_service_url_is_accepted(url):
    assert parse_service_url(url) == url.rstrip('/')

@pytest.mark.parametrize('url', [
    'ftp://localhost:8000',
    'localhost:8000',
    'http://example.com:8000',
    'http://localhost:8000/game',
    'http://user:password@localhost:8000',
    'http://localhost:70000'
])
def test_invalid_service_url_is_rejected(url):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_service_url(url)

def test_match_report_contains_winner_and_shot(capsys):
    result = MatchResult(
        starting_player=0,
        winner=0,
        outcome='victory',
        reason='Opponent fleet destroyed',
        shots = [{
            'player': 0,
            'coordinate': 'J10',
            'expected': 'killed',
            'reported': 'killed'
        }]
    )

    print_match_result(result, ('Альфа', 'Бета'))

    output = capsys.readouterr().out

    assert 'Победитель: Альфа' in output
    assert 'J10' in output
    assert 'ожидалось killed, получено killed' in output
    assert 'Проверено выстрелов: 1' in output
    assert 'Закрытие известных сессий: без ошибок' in output

def test_tournament_command_arguments():
    args = build_parser().parse_args(
        [
            'tournament',
            '--players',
            'arena/players.local.json',
            '--seed',
            '42',
            '--allow-shared-service'
        ]
    )

    assert args.command == 'tournament'
    assert args.players == 'arena/players.local.json'
    assert args.seed == 42
    assert args.allow_shared_service is True

def test_tournament_report_contains_table_and_winner(capsys):
    first = Participant('Альфа', 'http://localhost:8000')
    second = Participant('Бета', 'http://localhost:8001')

    game = MatchResult(
        starting_player=0,
        winner=0,
        outcome='victory',
        reason='Opponent fleet destroyed'
    )

    result = TournamentResult(
        standings=[
            Standing(
                participant=first,
                played=1,
                wins=1,
                points=1,
                rank=1
            ),
            Standing(
                participant=second,
                played=1,
                losses=1,
                rank=2
            )
        ],
        matches=[
            TournamentMatch(
                first=first,
                second=second,
                result=game
            )
        ]
    )

    print_tournament_result(result)

    output = capsys.readouterr().out

    assert 'Итоговая таблица:' in output
    assert 'Проведено матчей: 1' in output
    assert 'Победитель турнира: Альфа' in output
    assert 'Альфа против Бета' in output

def test_unresolved_tournament_does_not_annouce_winner(capsys):
    first = Participant('Альфа', 'http://localhost:8000')
    second = Participant('Бета', 'http://localhost:8001')

    result = TournamentResult(
        standings=[
            Standing(
                participant=first,
                played=1,
                unresolved=1,
                rank=1
            ),
            Standing(
                participant=second,
                played=1,
                unresolved=1,
                rank=1
            )
        ],
        matches=[
            TournamentMatch(
                first=first,
                second=second,
                result=MatchResult(
                    starting_player=0,
                    outcome='double_failure'
                )
            )
        ]
    )
    print_tournament_result(result)

    output = capsys.readouterr().out

    assert 'Матчей без победителя: 1' in output
    assert 'Итоговый победитель турнира пока не определён' in output
    assert 'Победитель турнира:' not in output

def test_tournament_report_argument():
    args = build_parser().parse_args([
        'tournament',
        '--players',
        'arena/players.local.json',
        '--report',
        'reports/tournament.json'
    ])

    assert args.report == 'reports/tournament.json'