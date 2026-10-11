import json

import pytest

from arena.config import load_participants

VALID_PLAYERS = [
    {
        'name': 'Альфа',
        'base_url': 'http://localhost:8000'
    },
    {
        'name': 'Бета',
        'base_url': 'http://localhost:8001'
    }
]

@pytest.mark.parametrize('encoding', ['utf-8', 'utf-8-sig'])
def test_participants_file_is_loaded(tmp_path, encoding):
    path = tmp_path / 'players.json'

    path.write_text(json.dumps(VALID_PLAYERS, ensure_ascii=False), encoding=encoding)

    participants = load_participants(path)

    assert [player.name for player in participants] == ['Альфа', 'Бета']
    assert [player.base_url for player in participants] == [
        'http://localhost:8000',
        'http://localhost:8001'
    ]

@pytest.mark.parametrize(
    'data',
    [
        None,
        {},
        [],
        [VALID_PLAYERS[0]],
        [42, VALID_PLAYERS[1]],
        [{'name': 'Альфа'}, VALID_PLAYERS[1]],
        [{'name': 'Альфа', 'base_url': 8000}, VALID_PLAYERS[1]],
        [
            {
                'name': 'Альфа',
                'base_url': 'http://localhost:8000',
                'extra': True
            },
            VALID_PLAYERS[1]
        ]
    ]
)
def test_invalid_participants_file_is_rejected(tmp_path, data):
    path = tmp_path / 'players.json'

    path.write_text(json.dumps(data), encoding='utf-8')

    with pytest.raises(ValueError):
        load_participants(path)

def test_invalid_json_is_rejected(tmp_path):
    path = tmp_path / 'players.json'
    path.write_text('[{"name":', encoding='utf-8')

    with pytest.raises(ValueError, match='Invalid participants JSON'):
        load_participants(path)

def test_missing_file_is_rejected(tmp_path):
    path = tmp_path / 'missing.json'

    with pytest.raises(ValueError, match='Cannot read'):
        load_participants(path)