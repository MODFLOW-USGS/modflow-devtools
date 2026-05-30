from boltons.dictutils import OMD

from modflow_devtools.dfn import Dfn


def test_load_dfn(dfn_dir):
    common = {}
    common_path = dfn_dir / "common.dfn"
    if common_path.exists():
        with common_path.open() as f:
            common, _ = Dfn.load_dfn(f)

    names = [p.stem for p in dfn_dir.glob("*.dfn") if p.stem not in ("common", "flopy")]
    assert names

    empty = ["exg-gwfprt", "exg-gwfgwt", "exg-gwfgwe", "sln-ems"]
    for name in names:
        with (dfn_dir / f"{name}.dfn").open() as f:
            dfn, meta = Dfn.load_dfn(f, common=common)
        assert isinstance(dfn, OMD)
        assert isinstance(meta, list)
        assert any(dfn) == (name not in empty), name


def test_load(dfn_dir):
    name = "sim-nam"
    with (dfn_dir / f"{name}.dfn").open() as f:
        dfn = Dfn.load(f, schema_version="1")
        assert any(dfn)
        assert dfn["continue"]["block"] == "options"

        f.seek(0)
        dfn = Dfn.load(f, name=name)  # defaults to 2.0.0.dev0
        assert any(dfn)
        assert dfn["name"] == name
        assert dfn["schema_version"] == "2.0.0.dev0"
        assert dfn["options"]["continue"]["block"] == "options"

        f.seek(0)
        dfn = Dfn.load(f, name=name, schema_version="2.0.0.dev0")
        assert any(dfn)
        assert dfn["name"] == name
        assert dfn["schema_version"] == "2.0.0.dev0"
        assert dfn["options"]["continue"]["block"] == "options"

        f.seek(0)
        dfn = Dfn.load(f, name=name, schema_version="2.0.0.dev1")
        assert any(dfn)
        assert dfn["name"] == name
        assert dfn["schema_version"] == "2.0.0.dev1"
        assert dfn["blocks"]["options"]["continue"]["block"] == "options"


def test_load_all(dfn_dir):
    dfns = Dfn.load_all(dfn_dir, schema_version="1")
    assert len(dfns) > 1
    sim = dfns["sim-nam"]
    assert any(sim)
    assert sim["continue"]["block"] == "options"

    dfns = Dfn.load_all(dfn_dir)  # defaults to 2.0.0.dev0
    assert len(dfns) > 1
    sim = dfns["sim-nam"]
    assert any(sim)
    assert sim["schema_version"] == "2.0.0.dev0"
    assert sim["options"]["continue"]["block"] == "options"

    dfns = Dfn.load_all(dfn_dir, schema_version="2.0.0.dev0")
    assert len(dfns) > 1
    sim = dfns["sim-nam"]
    assert any(sim)
    assert sim["schema_version"] == "2.0.0.dev0"
    assert sim["options"]["continue"]["block"] == "options"

    dfns = Dfn.load_all(dfn_dir, schema_version="2.0.0.dev1")
    assert len(dfns) == 1
    sim = dfns["sim-nam"]
    assert any(sim)
    assert sim["schema_version"] == "2.0.0.dev1"
    assert sim["blocks"]["options"]["continue"]["block"] == "options"
