"""What the backend learns about the caller.

Deployments' authorization rules and header mappings read the OAUTH2_CLAIM_*
request headers mod_oauth2 sets, so those are part of what the image provides:
from JWT claims for ID tokens, and from the introspection response for access tokens.
"""

import pytest

from conftest import backend_headers

IDENTITY = {"email", "sub", "aud", "exp"}


def claims_received(response):
    headers = backend_headers(response)
    return {name.removeprefix("oauth2_claim_"): values
            for name, values in headers.items() if name.startswith("oauth2_claim_")}


@pytest.mark.parametrize("proxy", ["proxy-default", "proxy-chain"], indirect=True)
def test_access_token_claims_reach_backend(proxy, google):
    token = google.access_token()
    claims = claims_received(proxy.get("/api/x", token))
    for name in IDENTITY:
        assert claims.get(name) == [str(token.claims[name])], name


@pytest.mark.parametrize("proxy", ["proxy-chain", "proxy-minimal"], indirect=True)
def test_id_token_claims_reach_backend(proxy, google):
    token = google.id_token()
    claims = claims_received(proxy.get("/api/x", token))
    for name in IDENTITY:
        assert claims.get(name) == [str(token.claims[name])], name


@pytest.mark.parametrize("proxy", ["proxy-default"], indirect=True)
def test_site_conf_maps_claims_to_oidc_headers(proxy, google):
    token = google.access_token()
    headers = backend_headers(proxy.get("/api/x", token))
    assert headers["oidc_claim_email"] == [token.claims["email"]]
    assert headers["oidc_claim_user_id"] == [token.claims["sub"]]
    assert headers["oidc_claim_expires_in"] == [token.claims["exp"]]


@pytest.mark.parametrize("proxy", ["proxy-default", "proxy-chain"], indirect=True)
def test_client_cannot_inject_claims(proxy, google):
    token = google.access_token()
    spoofed = "attacker@example.com"
    headers = backend_headers(proxy.get("/api/x", token, headers={
        "OAUTH2_CLAIM_email": spoofed,
        "oidc_claim_email": spoofed,
        # Claims the token doesn't have must not get through either.
        "OAUTH2_CLAIM_admin": "true",
        "OAUTH2_CLAIM_access_token": "ya29.someone-elses",
    }))
    assert headers["oauth2_claim_email"] == [token.claims["email"]]
    assert headers["oidc_claim_email"] == [token.claims["email"]]
    assert "oauth2_claim_admin" not in headers
    assert headers["oauth2_claim_access_token"] == [token.value]
    assert headers["oidc_claim_access_token"] == [token.value]
