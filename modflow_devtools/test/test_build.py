import platform

from modflow_devtools.build import meson_build

system = platform.system()


def test_meson_build(modflow6_path, tmpdir):
    bld_path = tmpdir / "builddir"
    bin_path = tmpdir / "bin"
    lib_path = bin_path

    meson_build(modflow6_path, bld_path, bin_path, bin_path, quiet=False)

    # check  build directory was populated
    assert (bld_path / "build.ninja").is_file()
    assert (bld_path / "src").is_dir()
    assert (bld_path / "meson-logs").is_dir()

    # check binaries and libraries were created
    ext = ".exe" if system == "Windows" else ""
    for exe in ["mf6", "mf5to6", "zbud6"]:
        assert (bin_path / f"{exe}{ext}").is_file()
    assert (
        bin_path
        / (
            "libmf6"
            + (
                ".so"
                if system == "Linux"
                else (".dylib" if system == "Darwin" else "")
            )
        )
    ).is_file()
