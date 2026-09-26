"""The committed frontend contract (openapi.json, mock city fixtures) equals what the backend renders now."""

import pytest

from gridline.api.contract import contract_files
from tests.conftest import DATA_DIR

FRONTEND = DATA_DIR.parents[1] / "frontend"


@pytest.mark.skipif(not FRONTEND.is_dir(), reason="frontend/ is not checked out")
def test_committed_contract_files_are_current() -> None:
    stale = [
        relative
        for relative, content in contract_files(DATA_DIR).items()
        if not (FRONTEND / relative).exists() or (FRONTEND / relative).read_text(encoding="utf-8") != content
    ]
    assert not stale, f"regenerate with `npm run gen:api` in frontend/ (stale: {', '.join(stale)})"
