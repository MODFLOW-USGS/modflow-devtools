def test_toml_safe_primitives_pass_through():
    """_toml_safe passes primitive types through unchanged."""
    assert _toml_safe("hello") == "hello"
    assert _toml_safe(42) == 42
    assert _toml_safe(3.14) == 3.14
    assert _toml_safe(True) is True
    assert _toml_safe(None) is None


def test_toml_safe_non_primitive_coerced_to_str():
    """_toml_safe coerces non-TOML-native types (e.g. Version) to str."""
    assert _toml_safe(Version("1.1")) == "1.1"


def test_toml_safe_fieldbase_via_model_dump():
    """_toml_safe converts FieldBase instances via model_dump recursively."""
    kw = Keyword(name="save_flows", description="save flows")
    result = _toml_safe(kw)
    assert isinstance(result, dict)
    assert result["name"] == "save_flows"
    assert result["type"] == "keyword"


def test_toml_safe_nested():
    """_toml_safe recurses into dicts and lists."""
    obj = {"a": [Version("2"), "plain"], "b": {"c": 99}}
    result = _toml_safe(obj)
    assert result["a"][0] == "2"
    assert result["a"][1] == "plain"
    assert result["b"]["c"] == 99


def test_mapper_load_v1(dfn_name):
    with (
        (DFN_DIR / "common.dfn").open() as common_file,
        (DFN_DIR / f"{dfn_name}.dfn").open() as dfn_file,
    ):
        common = _load_common(common_file)
        dfn = load(dfn_file, name=dfn_name, format="dfn", common=common)
        assert any(dfn.fields) == (dfn.name not in EMPTY_DFNS)


def test_mapper_load_flat():
    dfns = load_flat(path=DFN_DIR)
    for dfn in dfns.values():
        assert any(dfn.fields) == (dfn.name not in EMPTY_DFNS)


def test_dfn_to_plain_dict_version_coerced_and_none_excluded():
    """Version is coerced to str; None fields are excluded from output."""
    dfn = DfnSpec(
        schema_version=Version("1.1"),
        name="test-dfn",
        parent=None,
        blocks=None,
    )
    d = _dfn_to_plain_dict(dfn)
    assert d["schema_version"] == "1.1"
    assert d["name"] == "test-dfn"
    assert "parent" not in d
    assert "blocks" not in d


def test_dfn_to_plain_dict_with_fieldbase_blocks():
    """FieldBase blocks are serialized via model_dump."""
    dfn = DfnSpec(
        schema_version=Version("2"),
        name="test-dfn",
        blocks={
            "options": {
                "nper": Integer(name="nper", description="number of periods"),
            }
        },
    )
    d = _dfn_to_plain_dict(dfn)
    block = d["blocks"]["options"]
    assert "nper" in block
    assert block["nper"]["type"] == "integer"
    assert block["nper"]["name"] == "nper"


def test_dfn_to_plain_dict_with_fieldv1_blocks():
    """FieldV1 blocks are serialized via dataclasses.asdict."""
    dfn = DfnSpec(
        schema_version=Version("1"),
        name="test-dfn",
        blocks={
            "options": {
                "save_flows": FieldV1(name="save_flows", type="keyword", block="options"),
            }
        },
    )
    d = _dfn_to_plain_dict(dfn)
    block = d["blocks"]["options"]
    assert "save_flows" in block
    assert block["save_flows"]["name"] == "save_flows"
    assert block["save_flows"]["type"] == "keyword"
