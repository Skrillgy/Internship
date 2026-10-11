import json

from arena.match import MatchResult
from arena.report import save_tournament_report
from arena.tournament import (
    Participant,
    Standing,
    TournamentMatch,
    TournamentResult
)

def make_tournament_result(game):
    players = [
        Participant('Альфа', 'http://localhost:8000'),
        Participant('Бета', 'http://localhost:8001')
    ]

    standings = []

    for index, player in enumerate(players):
        has_winner = game.winner is not None
        won = game.winner == index
        lost = has_winner and not won

        standings.append(
            Standing(
                participant=player,
                played=1,
                wins=int(won),
                losses=int(lost),
                unresolved=int(not has_winner),
                points=int(won),
                rank=1 if won or not has_winner else 2
            )
        )

    standings.sort(key=lambda standing: -standing.points)

    return TournamentResult(
        standings=standings,
        matches=[
            TournamentMatch(
                first=players[0],
                second=players[1],
                result=game
            )
        ]
    )

def test_report_preserves_table_and_shots(tmp_path):
    game = MatchResult(
        starting_player=0,
        winner=0,
        outcome='victory',
        reason='Флот противника потоплен',
        shots=[{
            'player': 0,
            'coordinate': 'j10',
            'expected': 'killed',
            'reported': 'killed'
        }]
    )

    result = make_tournament_result(game)
    path = tmp_path / 'reports' / 'tournament.json'

    saved_path = save_tournament_report(result, path)

    assert saved_path == path

    text = path.read_text(encoding='utf-8')
    document = json.loads(text)

    assert 'Альфа' in text
    assert document['schema_version'] == 1
    assert document['report_type'] == 'tournament'
    assert document['saved_at']

    table = document['result']['standings']

    assert table[0]['participant']['name'] == 'Альфа'
    assert table[0]['points'] == 1
    assert table[1]['losses'] == 1

    match = document['result']['matches'][0]['result']

    assert match['winner'] == 0
    assert match['reason'] == 'Флот противника потоплен'
    assert match['shots'] == game.shots

def test_report_preserves_violations_and_cleanup_errors(tmp_path):
    game = MatchResult(
        starting_player=0,
        winner=1,
        outcome='techical',
        reason='Request timeout',
        violations={0: 'timeout'},
        close_errors={0: 'Cannot close session'}
    )

    path = tmp_path / 'tournament.json'
    save_tournament_report(make_tournament_result(game), path)

    document = json.loads(path.read_text(encoding='utf-8'))
    match = document['result']['matches'][0]['result']

    assert match['winner'] == 1
    assert match['outcome'] == 'techical'
    assert match['violations'] == {'0': 'timeout'}
    assert match['close_errors'] == {'0': 'Cannot close session'}

def test_report_preserves_match_without_winner(tmp_path):
    game = MatchResult(
        starting_player=0,
        outcome='double_failure',
        reason='Both paraticipans failed to start',
        violations={0: 'timeout', 1: 'timeout'}
    )

    path = tmp_path / 'tournament.json'
    save_tournament_report(make_tournament_result(game), path)

    document = json.loads(path.read_text(encoding='utf-8'))

    match = document['result']['matches'][0]['result']
    table = document['result']['standings']

    assert match['winner'] is None
    assert all(standing['points'] == 0 for standing in table)
    assert all(standing['unresolved'] == 1 for standing in table)