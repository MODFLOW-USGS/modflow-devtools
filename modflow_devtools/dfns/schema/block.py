from collections.abc import Mapping

from modflow_devtools.dfns.schema.field import Fields

Block = Fields
Blocks = Mapping[str, Block]


def block_sort_key(item) -> int:
    k, _ = item
    if k == "options":
        return 0
    elif "period" in k:
        return 2
    else:
        return 1
