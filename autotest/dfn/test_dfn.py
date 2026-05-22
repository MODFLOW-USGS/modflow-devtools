from modflow_devtools.dfn import Dfn
from modflow_devtools.markers import requires_pkg


@requires_pkg("boltons")
def test_load_v1(dfn_dir):
    common = {}
    common_path = dfn_dir / "common.dfn"
    if common_path.exists():
        with common_path.open() as f:
            common, _ = Dfn._load_v1_flat(f)
    names = [p.stem for p in dfn_dir.glob("*.dfn") if p.stem not in ("common", "flopy")]
    assert names
    for name in names:
        with (dfn_dir / f"{name}.dfn").open() as f:
            dfn = Dfn.load(f, name=name, common=common)
        assert any(dfn)


@requires_pkg("boltons")
def test_load_all(dfn_dir):
    dfns = Dfn.load_all(dfn_dir)
    assert any(dfns)
