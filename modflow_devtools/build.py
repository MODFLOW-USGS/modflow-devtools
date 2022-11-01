import subprocess
import sys
from os import PathLike
from pathlib import Path

from modflow_devtools.misc import set_dir


def meson_build(
    prj_path: PathLike = ".",
    bld_path: PathLike = "build",
    bin_path: PathLike = "bin",
    lib_path: PathLike = "bin",
    quiet: bool = True,
):
    """
    Setup, compile and install with meson.
    """

    prj_path = Path(prj_path).expanduser().absolute()
    bld_path = Path(bld_path).expanduser().absolute()
    bin_path = Path(bin_path).expanduser().absolute()
    lib_path = Path(lib_path).expanduser().absolute()

    with set_dir(prj_path):
        cmd = (
            f"meson setup {bld_path} "
            + f"--bindir={bin_path} "
            + f"--libdir={lib_path} "
            + "--prefix="
            + ("%CD%" if sys.platform.lower() == "win32" else "$(pwd)")
        )
        if not quiet:
            print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

        cmd = f"meson install -C {bld_path}"
        if not quiet:
            print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
