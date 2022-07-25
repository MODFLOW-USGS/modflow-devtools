import json
import os
import pathlib
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from contextlib import contextmanager

from .download import download_and_unzip, getmfexes
from .usgsprograms import usgs_program_data


class MFTestExe:
    """update and/or verify regression executables for test"""

    def __init__(
        self,
        releasebin: str = None,
        builtbin: str = None,
        targets: object = None,
    ):
        """MFTestExe init"""

        self._releasebin = releasebin
        self._builtbin = builtbin
        self._targets = targets
        self._working_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "temp")
        )

    def verify_exe(self):
        """
        verify downloaded and built exe exist
        """
        if not (
            os.path.isdir(self._releasebin) or os.path.isdir(self._builtbin)
        ):
            return False

        for t in self._targets.release_exe_names():
            if not os.path.isfile(os.path.join(self._releasebin, t)):
                return False

        for t in self._targets.regression_exe_names():
            if not os.path.isfile(os.path.join(self._builtbin, t)):
                return False

        return True

    def releases_current(self):
        """
        check downloaded versions against local db versions
        """
        try:
            with open(os.path.join(self._releasebin, "code.json")) as fh:
                release_d = json.load(fh)
        except:
            return False

        program_d = usgs_program_data.get_program_dict()
        exe_d = self._targets.target_exe_d()
        if release_d and program_d:
            for t in exe_d:
                if t in release_d:
                    key = t
                elif exe_d[t]["exe"] in release_d:
                    key = exe_d[t]["exe"]
                if (
                    key not in release_d
                    or release_d[key]["version"] != program_d[key]["version"]
                ):
                    return False

            return True

        return False

    def download_releases(self):
        """
        download mf released exe and copy to bin path
        """
        self._download_exes()

    def build_mf6_release(self):
        """
        download mf6 release source and build exe
        """
        self._build_mf6_release()

    def cleanup(self):
        """
        remove bins when possible
        """
        shutil.rmtree(self._builtbin, ignore_errors=True)
        shutil.rmtree(self._releasebin, ignore_errors=True)

    def _create_dirs(self):
        pths = [self._releasebin, self._working_dir]
        for pth in pths:
            print(f"creating... {os.path.abspath(pth)}")
            os.makedirs(pth, exist_ok=True)
            errmsg = f"could not create... {os.path.abspath(pth)}"
            assert os.path.exists(pth), errmsg

    def _download_exes(self):
        self._create_dirs()
        mfexe_pth = os.path.join(self._working_dir, "testing")
        getmfexes(mfexe_pth, verify=False)
        for target in os.listdir(mfexe_pth):
            srcpth = os.path.join(mfexe_pth, target)
            if os.path.isfile(srcpth):
                dstpth = os.path.join(self._releasebin, target)
                print(f"copying {srcpth} -> {dstpth}")
                shutil.copy(srcpth, dstpth)

    @contextmanager
    def _set_directory(self, path: str):
        origin = os.path.abspath(os.getcwd())
        path = os.path.abspath(path)
        try:
            os.chdir(path)
            print(f"change from {origin} -> {path}")
            yield
        finally:
            os.chdir(origin)
            print(f"change from {path} -> {origin}")

    def _set_compiler_environment_variable(self):
        fc = None

        # parse command line arguments
        for idx, arg in enumerate(sys.argv):
            if arg.lower() == "-fc":
                fc = sys.argv[idx + 1]
            elif arg.lower().startswith("-fc="):
                fc = arg.split("=")[1]

        # determine if fc needs to be set to the FC environmental variable
        env_var = os.getenv("FC", default="gfortran")
        if fc is None and fc != env_var:
            fc = env_var

        # validate Fortran compiler
        fc_options = (
            "gfortran",
            "ifort",
        )
        if fc not in fc_options:
            raise ValueError(
                f"Fortran compiler {fc} not supported. Fortran compile must be "
                + f"[{', '.join(str(value) for value in fc_options)}]."
            )

        # set FC environment variable
        os.environ["FC"] = fc

    def _meson_build(
        self,
        dir_path: str = "..",
        libdir: str = "bin",
    ):
        self._set_compiler_environment_variable()
        is_windows = sys.platform.lower() == "win32"
        with self._set_directory(dir_path):
            cmd = (
                "meson setup builddir "
                + f"--bindir={os.path.abspath(libdir)} "
                + f"--libdir={os.path.abspath(libdir)} "
                + "--prefix="
            )
            if is_windows:
                cmd += "%CD%"
            else:
                cmd += "$(pwd)"
            if pathlib.Path("builddir").is_dir():
                cmd += " --wipe"
            print(f"setup meson\nrunning...\n  {cmd}")
            subprocess.run(cmd, shell=True, check=True)

            cmd = "meson install -C builddir"
            print(f"build and install with meson\nrunning...\n  {cmd}")
            subprocess.run(cmd, shell=True, check=True)

    def _build_mf6_release(self):
        target_dict = usgs_program_data.get_target("mf6")

        download_and_unzip(
            target_dict["url"],
            pth=self._working_dir,
            verbose=True,
        )

        # update IDEVELOP MODE in the release
        srcpth = os.path.join(
            self._working_dir, target_dict["dirname"], target_dict["srcdir"]
        )
        fpth = os.path.join(srcpth, "Utilities", "version.f90")
        with open(fpth) as f:
            lines = f.read().splitlines()
        assert len(lines) > 0, f"could not update {srcpth}"

        f = open(fpth, "w")
        for line in lines:
            tag = "IDEVELOPMODE = 0"
            if tag in line:
                line = line.replace(tag, "IDEVELOPMODE = 1")
            f.write(f"{line}\n")
        f.close()

        # build release source files with Meson
        root_path = os.path.join(self._working_dir, target_dict["dirname"])
        self._meson_build(
            dir_path=root_path, libdir=os.path.abspath(self._builtbin)
        )


def parse_args():

    bindir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "bin")
    )

    parser = ArgumentParser(
        description="create bin directory of downloaded "
        + "mf executables and official mf6 "
        + "release built from source"
    )
    parser.add_argument(
        "-b",
        "--bin",
        required=False,
        default=bindir,
        help="bin path for executables",
    )
    parser.add_argument(
        "-i",
        "--iconic",
        action="store_true",
        required=False,
        help="iconic bin directory structure",
    )
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        required=False,
        help="remove existing bin dirs before update",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.iconic:
        releasebin = os.path.join(args.bin, "downloaded")
    else:
        releasebin = args.bin

    exe = MFTestExe(
        releasebin=releasebin, builtbin=os.path.join(args.bin, "rebuilt")
    )
    if args.cleanup:
        exe.cleanup()
    exe.download_releases()
    exe.build_mf6_release()
