"""The introspection endpoint's contract (RFC 7662), whatever implements it.

mod_oauth2 calls the endpoint from inside the container, so these tests do too.
"""

import json

import pytest

pytestmark = pytest.mark.parametrize("proxy", ["proxy-default"], indirect=True)


def test_valid_token_is_active_with_googles_claims(proxy, google):
    token = google.access_token()
    status, headers, body = proxy.introspect("--data-urlencode", f"token={token.value}")
    assert status == 200
    assert headers["content-type"] == "application/json; charset=utf-8"
    info = token.claims
    assert json.loads(body) == {
        "active": True,
        "scope": info["scope"],
        "sub": info["sub"],
        "username": info["email"],
        "email": info["email"],
        "exp": info["exp"],
        "token_type": "bearer",
        "aud": info["aud"],
    }
    assert google.tokeninfo_calls() == 1


@pytest.mark.parametrize("form", [
    pytest.param(["--data-urlencode", "token=ya29.unknown"], id="unknown token"),
    pytest.param(["--data-urlencode", "token="], id="empty token"),
    pytest.param(["--data", ""], id="no token"),
])
def test_invalid_token_is_inactive(proxy, google, form):
    status, _, body = proxy.introspect(*form)
    assert (status, json.loads(body)) == (200, {"active": False})


def test_google_unavailable_is_inactive(proxy, google):
    token = google.access_token()
    with google.tokeninfo_unavailable():
        status, _, body = proxy.introspect("--data-urlencode", f"token={token.value}")
    assert (status, json.loads(body)) == (200, {"active": False})


def test_only_post_is_supported(proxy):
    result = proxy.stack.exec(proxy.service, "curl", "-sk", "-w", "\n%{http_code}",
                              "https://127.0.0.1/introspect/")
    body, status = result.stdout.rsplit("\n", 1)
    assert (status, body) == ("500", "only POST supported")


def test_response_does_not_advertise_the_implementation(proxy, google):
    _, headers, _ = proxy.introspect("--data-urlencode", "token=ya29.unknown")
    assert headers["server"] == "Apache"
    assert "x-powered-by" not in headers
