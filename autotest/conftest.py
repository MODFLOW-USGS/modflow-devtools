from pathlib import Path

pytest_plugins = ["modflow_devtools.fixtures", "modflow_devtools.snapshots"]
project_root_path = Path(__file__).parent
