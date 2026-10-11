import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from arena.tournament import TournamentResult

def save_tournament_report(
        result: TournamentResult,
        path: str | Path
) -> Path:
    report_path = Path(path)

    document = {
        'schema_version': 1,
        'report_type': 'tournament',
        'saved_at': datetime.now(timezone.utc).isoformat(),
        'result': asdict(result)
    }

    content = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        allow_nan=False
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=report_path.parent,
            prefix=f'.{report_path.name}.',
            suffix='.tmp',
            delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.write('\n')

        temporary_path.replace(report_path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return report_path