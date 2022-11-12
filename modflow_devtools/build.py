import platform
import subprocess
from os import PathLike
from pathlib import Path

from modflow_devtools.misc import set_dir


def meson_build(
    project_path: PathLike,
    build_path: PathLike,
    bin_path: PathLike,
):
    project_path = Path(project_path).expanduser().absolute()
    build_path = Path(build_path).expanduser().absolute()
    bin_path = Path(bin_path).expanduser().absolute()

    with set_dir(Path(project_path)):
        cmd = (
            f"meson setup {build_path} "
            + f"--bindir={bin_path} "
            + f"--libdir={bin_path} "
            + f"--prefix={('%CD%' if platform.system() == 'Windows' else '$(pwd)')}"
            + (" --wipe" if build_path.is_dir() else "")
        )
        print(f"Running meson setup command: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

        cmd = f"meson install -C {build_path}"
        print(f"Running meson install command: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
