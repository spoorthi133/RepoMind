from app.static_analysis import ESLINT_CONFIG_NAMES, _has_eslint_config, _relpath


def test_relpath_with_repo_relative_raw_path(tmp_path):
    assert _relpath(tmp_path, "sub/file.py") == "sub/file.py"


def test_relpath_with_absolute_raw_path(tmp_path):
    absolute = str((tmp_path / "sub" / "file.py"))
    assert _relpath(tmp_path, absolute) == "sub/file.py"


def test_relpath_outside_repo_root_falls_back_to_raw_path(tmp_path):
    outside = str(tmp_path.parent / "elsewhere.py")
    assert _relpath(tmp_path, outside) == outside


def test_has_eslint_config_false_when_absent(tmp_path):
    assert _has_eslint_config(tmp_path) is False


def test_has_eslint_config_true_when_present(tmp_path):
    (tmp_path / ESLINT_CONFIG_NAMES[0]).write_text("module.exports = {};")
    assert _has_eslint_config(tmp_path) is True
