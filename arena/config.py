import json
from pathlib import Path

from arena.tournament import Participant

def load_participants(path: str | Path) -> list[Participant]:
    config_path = Path(path)

    try:
        text = config_path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise ValueError(f'Cannot read participants file: {config_path}') from exc

    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid participants JSON') from exc

    if not isinstance(data, list):
        raise ValueError('Participants JSON must contain a list')

    if len(data) < 2:
        raise ValueError('At least two participants are required')

    participants = []

    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f'Participant {index} must be an object')

        if set(item) != {'name', 'base_url'}:
            raise ValueError(
                f'Participant {index} must contain '
                f'name and base_url'
            )

        try:
            participant = Participant(
                name=item['name'],
                base_url=item['base_url']
            )
        except ValueError as exc:
            raise ValueError(f'Participant {index}: {exc}') from exc

        participants.append(participant)

    return participants