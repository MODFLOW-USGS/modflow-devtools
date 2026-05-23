"""Generate modflow_devtools/dfns/schema.json from the Pydantic models.

Run with:
    python scripts/generate_dfn_schema.py
"""

import json
from pathlib import Path

from pydantic import TypeAdapter

from modflow_devtools.dfns.schema import Component

_repo_root = Path(__file__).parent.parent
_schema_path = _repo_root / "modflow_devtools" / "dfns" / "schema.json"
_schema_id = "https://raw.githubusercontent.com/MODFLOW-ORG/modflow-devtools/main/modflow_devtools/dfns/schema.json"


def generate() -> dict:
    ta = TypeAdapter(Component)
    schema = ta.json_schema(mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": _schema_id,
        "title": "MODFLOW 6 definition file (v2)",
        "description": "Schema for MODFLOW 6 component definition files (DFNs), schema version 2.",
        **schema,
    }


def main():
    schema = generate()
    _schema_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Written to {_schema_path}")


if __name__ == "__main__":
    main()
