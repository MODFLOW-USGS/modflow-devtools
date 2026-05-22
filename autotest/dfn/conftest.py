import pytest

from modflow_devtools.dfn import fetch_dfns

MF6_OWNER = "MODFLOW-ORG"
MF6_REPO = "modflow6"
MF6_REF = "develop"


@pytest.fixture(scope="module")
def dfn_dir(module_tmpdir):
    pytest.importorskip("boltons")
    path = module_tmpdir / "dfn"
    path.mkdir()
    fetch_dfns(MF6_OWNER, MF6_REPO, MF6_REF, path, verbose=True)
    return path
