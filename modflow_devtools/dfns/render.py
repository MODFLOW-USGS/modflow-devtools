from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modflow_devtools.dfns.schema import (
        Array,
        Block,
        Field,
        Record,
        Union,
    )


def _shape(field: Array) -> str:
    return f"({', '.join(field.shape)})" if field.shape else ""


def _inline(field: Field) -> str:
    """Render a field as a token within a record row."""
    from modflow_devtools.dfns.schema import (
        Array,
        Double,
        File,
        Integer,
        Keyword,
        Record,
        String,
        Union,
    )

    match field:
        case Keyword():
            token = field.name.upper()
        case Array():
            token = f"<{field.name}{_shape(field)}>"
        case String() | Integer() | Double():
            token = f"<{field.name}>"
        case File():
            # file name (uppercased) acts as the keyword in the record row
            token = f"{field.name.upper()} {field.mode.upper()} <{field.name}>"
        case Record():
            token = " ".join(_inline(f) for f in field.fields.values())
        case Union():
            # Nested union inside a record: collapse to a single placeholder
            token = f"<{field.name}>"
        case _:
            token = f"<{field.name}>"

    return f"[{token}]" if field.optional else token


def _render_row(item: Record | Union) -> list[str]:
    """Return one or more rendered row strings for a List item.

    A Union whose arms are all Records produces one row per arm (each wrapped
    in [...] since arms are mutually exclusive alternatives).  A Union whose
    arms are scalars/keywords collapses to a single <name> placeholder — listing
    every option inline would be noise.
    """
    from modflow_devtools.dfns.schema import Record

    if isinstance(item, Record):
        return [" ".join(_inline(f) for f in item.fields.values())]

    # Union
    if all(isinstance(arm, Record) for arm in item.arms.values()):
        rows = []
        for arm in item.arms.values():
            row = " ".join(_inline(f) for f in arm.fields.values())
            rows.append(f"[{row}]")
        return rows
    else:
        return [f"<{item.name}>"]


def _render_field(field: Field, indent: str = "  ") -> str:
    """Render a top-level block field as one or more indented lines."""
    from modflow_devtools.dfns.schema import (
        Array,
        Double,
        File,
        Integer,
        Keyword,
        List,
        Record,
        String,
        Union,
    )

    def _wrap(token: str) -> str:
        return f"[{token}]" if field.optional else token

    match field:
        case Keyword():
            return f"{indent}{_wrap(field.name.upper())}"

        case String() | Integer() | Double():
            if field.tagged:
                inner = f"{field.name.upper()} <{field.name}>"
            else:
                inner = f"<{field.name}>"
            return f"{indent}{_wrap(inner)}"

        case File():
            inner = f"{field.mode.upper()} <{field.name}>"
            return f"{indent}{_wrap(inner)}"

        case Array():
            if field.shape:
                # Fixed-size array: READARRAY two-line format
                header = field.name.upper()
                body = f"{header}\n{indent}  <{field.name}{_shape(field)}> -- READARRAY"
                return f"{indent}{_wrap(body)}"
            else:
                # Inline variable-length array (e.g. AUXILIARY name1 name2 ...)
                if field.tagged:
                    inner = f"{field.name.upper()} <{field.name}>"
                else:
                    inner = f"<{field.name}>"
                return f"{indent}{_wrap(inner)}"

        case Record():
            inner = " ".join(_inline(f) for f in field.fields.values())
            return f"{indent}{_wrap(inner)}"

        case Union():
            lines = []
            for arm in field.arms.values():
                if isinstance(arm, Record):
                    inner = " ".join(_inline(f) for f in arm.fields.values())
                else:
                    inner = arm.name.upper() if isinstance(arm, Keyword) else f"<{arm.name}>"
                lines.append(f"{indent}{_wrap(inner)}")
            return "\n".join(lines)

        case List():
            rows = _render_row(field.item)
            if len(rows) > 1:
                # Union of Records: show each alternative once, no ellipsis
                return "\n".join(f"{indent}{r}" for r in rows)
            else:
                r = rows[0]
                return f"{indent}{r}\n{indent}{r}\n{indent}..."

        case _:
            return f"{indent}<{field.name}>"


def render_block(block: Block) -> str:
    """Render a Block as a BEGIN/END template string.

    Example output::

        BEGIN OPTIONS
          [AUXILIARY <auxnames(naux)>]
          [BOUNDNAMES]
          [PRINT_INPUT]
        END OPTIONS
    """
    lines = [f"BEGIN {block.name.upper()}"]
    for field in block.fields.values():
        lines.append(_render_field(field))
    lines.append(f"END {block.name.upper()}")
    return "\n".join(lines)
