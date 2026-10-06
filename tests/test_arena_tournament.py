import asyncio

import pytest

from arena.match import MatchResult
from arena.tournament import Participant, run_tournament

@pytest.fixture
def participants():
    return [
        Participant('Альфа', 'http://localhost:8000'),
        Participant('Бета', 'http://localhost:8001'),
        Participant('Гамма', 'http://localhost:8002')
    ]

def test_every_pair_plays_once_and_points_are_counted(monkeypatch, participants):
    calls = []

    async def fake_match(first, second, *, starting_player):
        calls.append((first.base_url, second.base_url, starting_player))

        assert first is not second

        return MatchResult(
            starting_player=starting_player,
            winner=0,
            outcome='victory'
        )

    monkeypatch.setattr('arena.tournament.run_match', fake_match)

    result = asyncio.run(run_tournament(participants, seed=42))

    assert [(first, second) for first, second, _ in calls] == [
        ('http://localhost:8000', 'http://localhost:8001'),
        ('http://localhost:8000', 'http://localhost:8002'),
        ('http://localhost:8001', 'http://localhost:8002')
    ]
    assert all(start in (0, 1) for _, _, start in calls)
    assert len(result.matches) == 3

    table = {standing.participant.name: standing for standing in result.standings}

    assert table['Альфа'].points == 2
    assert table['Бета'].points == 1
    assert table['Гамма'].points == 0

    assert table['Альфа'].rank == 1
    assert table['Бета'].rank == 2
    assert table['Гамма'].rank == 3

    for standing in result.standings:
        assert standing.played == 2
        assert standing.played == (
            standing.wins
            + standing.losses
            + standing.unresolved
        )

def test_technocal_victory_gives_one_point(monkeypatch, participants):
    async def fake_match(first, second, *, starting_player):
        return MatchResult(
            starting_player=starting_player,
            winner=1,
            outcome='technical',
            violations={0, 'timeout'}
        )

    monkeypatch.setattr('arena.tournament.run_match', fake_match)

    result = asyncio.run(run_tournament(participants[:2]))

    winner, loser = result.standings

    assert winner.participant.name == 'Бета'
    assert winner.points == 1
    assert winner.wins == 1

    assert loser.points == 0
    assert loser.losses == 1

def test_failed_match_does_not_stop_tournament(monkeypatch, participants):
    calls = []

    async def fake_match(first, second, *, starting_player):
        calls.append((first.base_url, second.base_url))

        if len(calls) == 1:
            return MatchResult(
                starting_player=starting_player,
                outcome='double_failure',
                violations={0: 'timeout', 1: 'timeout'}
            )

        return MatchResult(
            starting_player=starting_player,
            winner=0,
            outcome='victory'
        )

    monkeypatch.setattr('arena.tournament.run_match', fake_match)

    result = asyncio.run(run_tournament(participants))

    assert len(calls) == 3
    assert len(result.matches) == 3
    assert sum(standing.points for standing in result.standings) == 2
    assert sum(standing.unresolved for standing in result.standings) == 2

def test_equal_points_have_equal_rank(monkeypatch, participants):
    winners = iter([0, 1, 0])

    async def fake_match(first, second, *, starting_player):
        return MatchResult(
            starting_player=starting_player,
            winner=next(winners),
            outcome='victory'
        )

    monkeypatch.setattr('arena.tournament.run_match', fake_match)

    result = asyncio.run(run_tournament(participants))

    assert [standing.points for standing in result.standings] == [1, 1, 1]
    assert [standing.rank for standing in result.standings] == [1, 1, 1]

@pytest.mark.parametrize(
    'players', [
        [Participant('Альфа', 'http://localhost:8000')],
        [
            Participant('Альфа', 'http://localhost:8000'),
            Participant('альфа', 'http://localhost:8001')
        ],
        [
            Participant('Альфа', 'http://localhost:8000'),
            Participant('Бета', 'http://localhost:8000')
        ]
    ]
)
def test_invalid_participant_list_is_rejected(players):
    with pytest.raises(ValueError):
        asyncio.run(run_tournament(players))

def test_shared_service_can_be_enabled_for_testing(monkeypatch):
    async def fake_match(first, second, *, starting_player):
        return MatchResult(
            starting_player=starting_player,
            winner=0,
            outcome='victory'
        )

    monkeypatch.setattr('arena.tournament.run_match', fake_match)

    players = [
        Participant('Альфа', 'http://localhost:8000'),
        Participant('Бета', 'http://localhost:8000')
    ]

    result = asyncio.run(run_tournament(players, allow_shared_service=True))

    assert len(result.matches) == 1
    assert result.standings[0].points == 1