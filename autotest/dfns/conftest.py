import os
from pathlib import Path

import pytest

from modflow_devtools.dfns import fetch_dfns

PROJ_ROOT = Path(__file__).parents[1]

DFNS_REPO = os.getenv("TEST_DFNS_REPO", "MODFLOW-ORG/modflow6")
DFNS_REF = os.getenv("TEST_DFNS_REF", "develop")
DFNS_SOURCE = os.getenv("TEST_DFNS_SOURCE", "modflow6")
DFNS_VERSION = os.getenv("TEST_DFNS_VERSION", "6.6.0")


@pytest.fixture(scope="module")
def dfn_dir(module_tmpdir):
    """
    Path to DFN files: $DFNS_PATH if set, otherwise fetched from develop branch
    to a temp dir (for LocalDfnRegistry tests).
    """
    env_var = "DFNS_PATH"
    if dfns_path := os.getenv(env_var):
        dfn_path = Path(dfns_path).expanduser().resolve()
        assert dfn_path.exists(), f"{env_var}={dfns_path} does not exist"
        assert any(dfn_path.glob("*.dfn")), f"{env_var}={dfns_path} empty"
        return dfn_path

    dfns_path = module_tmpdir / "dfns"
    dfns_path.mkdir()
    owner = DFNS_REPO.split("/")[0]
    repo = DFNS_REPO.split("/")[1]
    fetch_dfns(owner, repo, DFNS_REF, dfns_path, verbose=True)
    return dfns_path
