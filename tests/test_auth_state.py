from djvrt.auth_state import _join_url


def test_join_url_normalizes_slashes() -> None:
    assert _join_url("http://example.test", "/accounts/login/") == "http://example.test/accounts/login/"
    assert _join_url("http://example.test/", "dashboard/") == "http://example.test/dashboard/"
