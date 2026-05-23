from modflow_devtools.dfn import schema as v1


def map_field(field: v1.Field) -> v1.Field:
    """
    Map a component field definition from the v1 schema to v1.1.
    This simply
    """

    return v1.Field(
        name=field["name"],
        type=field["type"],
        block=field.get("block"),
        default=field.get("default"),
        longname=field.get("longname"),
        description=field.get("description"),
        optional=field.get("optional", False),
        developmode=field.get("developmode", False),
        shape=field.get("shape"),
        valid=field.get("valid"),
        netcdf=field.get("netcdf", False),
        tagged=field.get("tagged", False),
    )


def map(dfn: v1.Dfn) -> v1.Dfn:
    """Map a component definition from the v1 schema to v1.1."""

    blocks: dict[str, dict] = {}
    for block_name, block_fields in (dfn["blocks"] or {}).items():
        blocks[block_name] = {
            field_name: map_field(field)
            for field_name, field in block_fields.items()
            if isinstance(field, dict)
        }

    for block_name, block_fields in blocks.items():
        dfn.setdefault(block_name, {})  # type: ignore[misc]
        for field_name, field_data in block_fields.items():
            dfn[block_name][field_name] = field_data  # type: ignore[literal-required]

    dfn["blocks"] = None  # cleared; _serialize_safe drops None, blocks are now top-level keys
    dfn["schema_version"] = "1.1"
    return dfn
