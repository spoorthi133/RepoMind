import pytest

from app.clone import clone_repo, repo_name_from_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/pallets/flask.git", "flask"),
        ("https://github.com/pallets/flask", "flask"),
        ("https://github.com/pallets/flask/", "flask"),
        ("git@github.com:pallets/flask.git", "flask"),
        ("https://github.com/pallets/some repo!.git", "some_repo_"),
    ],
)
def test_repo_name_from_url(url, expected):
    assert repo_name_from_url(url) == expected


def test_repo_name_from_url_empty_defaults_to_repo():
    assert repo_name_from_url("") == "repo"


def test_clone_repo_rejects_empty_url(tmp_path):
    with pytest.raises(ValueError):
        clone_repo("", tmp_path)


def test_clone_repo_rejects_flag_injection_url(tmp_path):
    with pytest.raises(ValueError):
        clone_repo("--upload-pack=evil", tmp_path)
