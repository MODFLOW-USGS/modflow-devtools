import os
import subprocess
import sys
from enum import Enum
from shutil import which


class MFTargetType(Enum):
    TEST = 1
    RELEASE = 2
    REGRESSION = 3


class MFTestTargets:
    """define test targets for modflow tests"""

    def __init__(
        self,
        testbin: str = None,
        releasebin: str = None,
        builtbin: str = None,
        use_path: bool = False,
    ):
        """MFTestTargets init"""

        self._exe_targets = {
            "mf6": {"exe": "mf6", "type": MFTargetType.TEST},
            "mf5to6": {"exe": "mf5to6", "type": MFTargetType.TEST},
            "zbud6": {"exe": "zbud6", "type": MFTargetType.TEST},
            "libmf6": {"exe": None, "type": MFTargetType.TEST},
            "mf2005": {"exe": "mf2005dbl", "type": MFTargetType.RELEASE},
            "mfnwt": {"exe": "mfnwtdbl", "type": MFTargetType.RELEASE},
            "mfusg": {"exe": "mfusgdbl", "type": MFTargetType.RELEASE},
            "mflgr": {"exe": "mflgrdbl", "type": MFTargetType.RELEASE},
            "mf2005s": {"exe": "mf2005", "type": MFTargetType.RELEASE},
            "mt3dms": {"exe": "mt3dms", "type": MFTargetType.RELEASE},
            "mf6-regression": {"exe": "mf6", "type": MFTargetType.REGRESSION},
        }

        self._testbin = testbin
        self._releasebin = releasebin
        self._builtbin = builtbin
        self._use_path = use_path
        self._target_path_d = None

    def set_targets(self):
        """
        set target paths from current bin directories
        """
        self._set_targets()

    def target_paths(self):
        """
        get the target path dictionary generated by set_targets
        """
        return self._target_path_d

    def get_mf6_version(self, version=None):
        """
        get version of mf6 entry in _exe_targets
        """
        return self._mf6_target_version(target=version)

    def target_exe_d(self):
        """
        get the _exe_targets dictionary
        """
        return self._exe_targets

    def release_exe_names(self):
        """
        get name list of release executables
        """
        target_ext, target_so = self._extensions()
        return [
            f"{self._exe_targets[t]['exe']}{target_ext}"
            for t in self._exe_targets
            if self._exe_targets[t]["type"] == MFTargetType.RELEASE
            and self._exe_targets[t]["exe"]
        ]

    def release_lib_names(self):
        """
        get name list of release libs
        """
        target_ext, target_so = self._extensions()
        return [
            f"{self._exe_targets[t]}{target_so}"
            for t in self._exe_targets
            if self._exe_targets[t]["type"] == MFTargetType.RELEASE
            and self._exe_targets[t]["exe"] is None
        ]

    def regression_exe_names(self):
        """
        get name list of regression executables
        """
        target_ext, target_so = self._extensions()
        return [
            f"{self._exe_targets[t]['exe']}{target_ext}"
            for t in self._exe_targets
            if self._exe_targets[t]["type"] == MFTargetType.REGRESSION
            and self._exe_targets[t]["exe"]
        ]

    def regression_lib_names(self):
        """
        get name list of regression libs
        """
        target_ext, target_so = self._extensions()
        return [
            f"{self._exe_targets[t]}{target_so}"
            for t in self._exe_targets
            if self._exe_targets[t]["type"] == MFTargetType.REGRESSION
            and self._exe_targets[t]["exe"] is None
        ]

    def _target_pth(self, target, target_t=None, is_lib=False):
        if target_t == MFTargetType.TEST:
            path = self._testbin
        elif target_t == MFTargetType.REGRESSION:
            path = self._builtbin
        elif target_t == MFTargetType.RELEASE:
            path = self._releasebin

        if self._use_path:
            exe_exists = which(target)
        else:
            exe_exists = which(target, path=path)

        if (
            exe_exists is None
            and is_lib
            and os.path.isfile(os.path.join(path, target))
        ):
            exe_exists = os.path.join(path, target)

        if exe_exists is None:
            print(target)
            raise Exception(
                f"{target} does not exist or is not executable in test context."
            )

        return os.path.abspath(exe_exists)

    def _run_exe(self, argv, ws="."):
        buff = []
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ws
        )
        result, error = proc.communicate()
        if result is not None:
            c = result.decode("utf-8")
            c = c.rstrip("\r\n")
            # print(f"{c}")
            buff.append(c)

        return proc.returncode, buff

    def _mf6_target_version(self, target=None):
        exe = self._target_path_d[target]
        return_code, buff = self._run_exe((exe, "-v"))
        if return_code == 0:
            version = buff[0].split()[1]
        else:
            version = None
        return version

    def _set_targets(self):
        self._target_path_d = None
        target_ext, target_so = self._extensions()

        self._target_path_d = {}
        for t in list(self._exe_targets):
            is_lib = False
            if self._exe_targets[t]["exe"] is None:
                name = f"{t}{target_so}"
                is_lib = True
            else:
                name = f"{self._exe_targets[t]['exe']}{target_ext}"

            target = self._target_pth(
                name, target_t=self._exe_targets[t]["type"], is_lib=is_lib
            )
            self._target_path_d[t] = target

    def _extensions(self):
        target_ext = ""
        target_so = ".so"
        sysinfo = sys.platform.lower()
        if sysinfo.lower() == "win32":
            target_ext = ".exe"
            target_so = ".dll"
        elif sysinfo.lower() == "darwin":
            target_so = ".dylib"

        return target_ext, target_so


class MFTestContext:
    """setup test context for modflow tests"""

    def __init__(
        self,
        testbin: str = None,
        use_path: bool = False,
        update_exe: bool = False,
    ):
        """MFTestContext init"""

        self._testbin = os.path.abspath(testbin)
        self._releasebin = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "bin")
        )

        builtbin = os.path.join(self._releasebin, "rebuilt")

        self._update = update_exe

        self._targets = MFTestTargets(
            testbin=testbin,
            releasebin=self._releasebin,
            builtbin=builtbin,
            use_path=use_path,
        )

        self._update_context()

    def get_target_dictionary(self):
        """
        get target path dictionary
        """
        return self._targets.target_paths()

    def get_mf6_version(self, version="mf6"):
        """
        get mf6 version
        """
        return self._targets.get_mf6_version(version=version)

    def _update_context(self):

        if not self._exe.verify_exe() or (
            self._update and not self._exe.releases_current()
        ):
            self._exe.cleanup()
            self._exe.download_releases()
            self._exe.build_mf6_release()

        self._targets.set_targets()
