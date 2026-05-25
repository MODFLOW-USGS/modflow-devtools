"""Tests for the DFNs CLI"""

# TODO expand


def test_main_help():
    from modflow_devtools.dfns.__main__ import main

    result = main([])
    assert result == 0


def test_info_command():
    from modflow_devtools.dfns.__main__ import main

    result = main(["info"])
    assert result == 0


def test_clean_command():
    from modflow_devtools.dfns.__main__ import main

    result = main(["clean"])
    assert result == 0
