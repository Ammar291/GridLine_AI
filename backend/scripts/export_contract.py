"""Write the backend's contract for the frontend: ``frontend/openapi.json`` and the mock-mode city fixtures.

Run from ``backend/``:  uv run python scripts/export_contract.py   (``npm run gen:api`` in frontend/ does this
and then regenerates ``src/api/schema.d.ts``). No database or network is needed.
"""

import sys
from pathlib import Path

from gridline.api.contract import contract_files
from gridline.config import Settings

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def main() -> int:
    for relative, content in contract_files(Settings().resolved_data_dir()).items():
        path = FRONTEND / relative
        changed = not path.exists() or path.read_text(encoding="utf-8") != content
        path.write_text(content, encoding="utf-8")
        print(f"{'wrote' if changed else 'unchanged'}  frontend/{relative}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
