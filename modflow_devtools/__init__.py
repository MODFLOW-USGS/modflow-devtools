"""modflow_devtools is a Python package containing tools for MODFLOW
development."""


from .framework import running_on_CI, set_teardown_test, testing_framework
from .simulation import Simulation
from .targets import get_mf6_version, run_exe, target_dict

# modflow_devtools
from .config import (
    __author__,
    __date__,
    __description__,
    __email__,
    __maintainer__,
    __status__,
    __version__,
)

# autotest
from .testing.testing import (
    compare,
    compare_budget,
    compare_concs,
    compare_heads,
    compare_stages,
    compare_swrbudget,
    get_entries_from_namefile,
    get_input_files,
    get_mf6_blockdata,
    get_mf6_comparison,
    get_mf6_files,
    get_mf6_ftypes,
    get_mf6_mshape,
    get_mf6_nper,
    get_namefiles,
    get_sim_name,
    setup,
    setup_comparison,
    setup_mf6,
    setup_mf6_comparison,
    teardown,
)

# define public interfaces
__all__ = [
    "__version__",
    # targets
    "run_exe",
    "get_mf6_version",
    "target_dict",
    # simulation
    "Simulation",
    # framework
    "running_on_CI",
    "set_teardown_test",
    "testing_framework",
    # testing
    "setup",
    "setup_comparison",
    "teardown",
    "get_namefiles",
    "get_entries_from_namefile",
    "get_sim_name",
    "get_input_files",
    "compare_budget",
    "compare_swrbudget",
    "compare_heads",
    "compare_concs",
    "compare_stages",
    "compare",
    "setup_mf6",
    "setup_mf6_comparison",
    "get_mf6_comparison",
    "get_mf6_files",
    "get_mf6_blockdata",
    "get_mf6_ftypes",
    "get_mf6_mshape",
    "get_mf6_nper",
]
