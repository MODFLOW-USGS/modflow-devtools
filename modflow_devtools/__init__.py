"""modflow_devtools is a Python package containing tools for MODFLOW
development."""

from .common_regression import (
    get_example_basedir,
    get_example_dirs,
    get_home_dir,
    get_select_dirs,
    get_select_packages,
    is_directory_available,
    set_mf6_regression,
)

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
from .framework import running_on_CI, set_teardown_test, testing_framework
from .mftest_context import MFTargetType, MFTestContext, MFTestTargets
from .simulation import Simulation
from .targets import get_mf6_version, get_target_dictionary, run_exe

# autotest
from .testing.budget_testing import eval_bud_diff
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
    model_setup,
    setup_comparison,
    setup_mf6,
    setup_mf6_comparison,
    teardown,
)
from .utilities.binary_file_writer import (
    uniform_flow_field,
    write_budget,
    write_head,
)
from .utilities.disu_util import get_disu_kwargs
from .utilities.download import (
    download_and_unzip,
    get_repo_assets,
    getmfexes,
    getmfnightly,
    repo_latest_version,
    zip_all,
)
from .utilities.mftest_exe import MFTestExe
from .utilities.usgsprograms import usgs_program_data

# define public interfaces
__all__ = [
    "__version__",
    "MFTestTargets",
    "MFTestExe",
    "MFTestContext",
    # common_regression
    "get_example_basedir",
    "get_example_dirs",
    "get_home_dir",
    "get_select_dirs",
    "get_select_packages",
    "is_directory_available",
    "set_mf6_regression",
    # targets
    "run_exe",
    "get_mf6_version",
    "get_target_dictionary",
    # simulation
    "Simulation",
    # framework
    "running_on_CI",
    "set_teardown_test",
    "testing_framework",
    # testing
    "eval_bud_diff",
    "model_setup",
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
    # utilities
    "uniform_flow_field",
    "write_head",
    "write_budget",
    "get_disu_kwargs",
    "usgs_program_data",
    "download_and_unzip",
    "getmfexes",
    "repo_latest_version",
    "get_repo_assets",
    "zip_all",
]
