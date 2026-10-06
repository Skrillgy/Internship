from dataclasses import dataclass, field
from itertools import combinations
from random import Random
from urllib.parse import urlsplit

from arena.client import ServiceClient
from arena.match import MatchResult, run_match

def service_key(base_url:str) -> tuple[str, str, int]:
    if not isinstance(base_url, str):
        raise ValueError('Service URL must be a string')

    try:
        url = urlsplit(base_url)
        port = url.port
    except ValueError as exc:
        raise ValueError('Invalid service URL') from exc

    if url.scheme not in {'http', 'https'}:
        raise ValueError('Service URL must use HTTP or HTTPS')

    if url.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Service must use a local address')

    if port is None or not 1 <= port <= 65535:
        raise ValueError('Service URL must specify a valid port')

    if (
        url.username is not None
        or url.password is not None
        or url.path not in {'', '/'}
        or url.query
        or url.fragment
    ):
        raise ValueError('Service URL must contain only host and port')

    host = url.hostname

    if host == 'localhost':
        host = '127.0.0.1'

    return url.scheme, host, port

@dataclass(frozen=True)
class Participant:
    name: str
    base_url: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('Participant name must not be empty')

        service_key(self.base_url)

        object.__setattr__(self, 'name', self.name.strip())
        object.__setattr__(self, 'base_url', self.base_url.rstrip('/'))

@dataclass
class Standing:
    participant: Participant
    played: int = 0
    wins: int = 0
    losses: int = 0
    unresolved: int = 0
    points: int = 0
    rank: int = 0

@dataclass
class TournamentMatch:
    first: Participant
    second: Participant
    result: MatchResult

@dataclass
class TournamentResult:
    standings: list[Standing]
    matches: list[TournamentMatch] = field(default_factory=list)

async def run_tournament(
        participants: list[Participant],
        *,
        seed: int | None = None,
        allow_shared_service: bool = False
) -> TournamentResult:
    if len(participants) < 2:
        raise ValueError('At least two participants are required')

    names = [participant.name.casefold() for participant in participants]

    if len(set(names)) != len(names):
        raise ValueError('Participant names must be unique')

    addresses = [service_key(participant.base_url) for participant in participants]

    if (not allow_shared_service and len(set(addresses)) != len(addresses)):
        raise ValueError('Each participant must have a separate service')

    standings = [Standing(participant=participant) for participant in participants]
    tournament = TournamentResult(standings=standings)
    random_source = Random(seed)

    for first_index, second_index in combinations(range(len(participants)), 2):
        first = participants[first_index]
        second = participants[second_index]

        async with (
            ServiceClient(first.base_url) as first_client,
            ServiceClient(second.base_url) as second_client
        ):
            result = await run_match(first_client, second_client, starting_player=random_source.randrange(2))

        tournament.matches.append(
            TournamentMatch(
                first=first,
                second=second,
                result=result
            )
        )

        first_standing = standings[first_index]
        second_standing = standings[second_index]

        first_standing.played += 1
        second_standing.played += 1

        if result.winner is None:
            first_standing.unresolved += 1
            second_standing.unresolved += 1
            continue

        if result.winner == 0:
            winner = first_standing
            loser = second_standing
        elif result.winner == 1:
            winner = second_standing
            loser = first_standing
        else:
            raise ValueError('Invalid winner index')

        winner.wins += 1
        winner.points += 1
        loser.losses += 1

    tournament.standings = sorted(
        standings,
        key=lambda standing: (-standing.points, standing.participant.name.casefold())
    )

    previous_points = None
    current_rank = 0

    for position, standing in enumerate(tournament.standings, start=1):
        if standing.points != previous_points:
            current_rank = position
            previous_points = standing.points

        standing.rank = current_rank

    return tournament