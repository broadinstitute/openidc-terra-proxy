"""When the proxy contacts Google to verify a bearer token, and what it caches.

Every test uses fresh tokens, because each proxy caches verified tokens for the
life of the container (mod_oauth2's shm cache, 300 s by default).
"""

import pytest

REPEATS = 5
DEFAULT_AND_CHAIN = pytest.mark.parametrize("proxy", ["proxy-default", "proxy-chain"], indirect=True)


@DEFAULT_AND_CHAIN
def test_valid_access_token_is_introspected_once_then_cached(proxy, google):
    token = google.access_token()
    statuses = [proxy.get("/api/x", token).status_code for _ in range(REPEATS)]
    assert statuses == [200] * REPEATS
    assert google.tokeninfo_calls() == 1


@DEFAULT_AND_CHAIN
def test_invalid_access_token_is_introspected_on_every_request(proxy, google):
    # Failures aren't cached, so each request with a bad token costs a call to Google.
    token = google.unknown_access_token()
    statuses = [proxy.get("/api/x", token).status_code for _ in range(REPEATS)]
    assert statuses == [401] * REPEATS
    assert google.tokeninfo_calls() == REPEATS


@DEFAULT_AND_CHAIN
def test_request_without_token_never_calls_google(proxy, google):
    assert proxy.get("/api/x").status_code == 401
    assert google.tokeninfo_calls() == 0


@DEFAULT_AND_CHAIN
def test_unauthenticated_location_never_verifies_the_token(proxy, google):
    token = google.access_token()
    assert proxy.get("/open/x", token).status_code == 200
    assert google.tokeninfo_calls() == 0


@DEFAULT_AND_CHAIN
def test_google_outage_is_not_cached(proxy, google):
    token = google.access_token()
    with google.tokeninfo_unavailable():
        assert proxy.get("/api/x", token).status_code == 401
    assert proxy.get("/api/x", token).status_code == 200
    assert google.tokeninfo_calls() == 2


@pytest.mark.parametrize("proxy", ["proxy-chain"], indirect=True)
def test_id_token_is_verified_locally(proxy, google):
    token = google.id_token()
    statuses = [proxy.get("/api/x", token).status_code for _ in range(REPEATS)]
    assert statuses == [200] * REPEATS
    assert google.tokeninfo_calls() == 0


@pytest.mark.parametrize("proxy", ["proxy-chain"], indirect=True)
@pytest.mark.parametrize("kind", ["expired", "forged"])
def test_rejected_id_token_falls_through_to_introspection(proxy, google, kind):
    # A JWT the metadata verifier rejects is still tried against introspection,
    # so bad JWTs also cost a call to Google on every request.
    token = google.id_token(exp=1_000_000_000) if kind == "expired" else google.forged_id_token()
    statuses = [proxy.get("/api/x", token).status_code for _ in range(REPEATS)]
    assert statuses == [401] * REPEATS
    assert google.tokeninfo_calls() == REPEATS


@pytest.mark.parametrize("proxy", ["proxy-default"], indirect=True)
def test_default_config_rejects_id_tokens(proxy, google):
    # The image's own oauth2.conf has no JWT verifier, so an ID token goes to
    # tokeninfo as if it were an access token, and Google rejects it.
    token = google.id_token()
    assert proxy.get("/api/x", token).status_code == 401
    assert google.tokeninfo_calls() == 1
