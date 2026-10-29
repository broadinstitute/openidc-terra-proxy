"""Fixtures: test PKI, the docker compose stack, the fake Google, and proxy clients.

The image under test is $PROXY_IMAGE (default openidc-terra-proxy:test). Build it first:
    docker build --platform linux/amd64 -f Dockerfile.ubi-minimal -t openidc-terra-proxy:test .
Set KEEP_STACK=1 to leave the containers running after the tests.
"""

import contextlib
import datetime
import ipaddress
import json
import os
import shutil
import ssl
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

TESTS = Path(__file__).parent
GENERATED = TESTS / ".generated"
IMAGE = os.environ.get("PROXY_IMAGE", "openidc-terra-proxy:test")
COMPOSE = ["docker", "compose", "-f", str(TESTS / "compose.yaml")]
PROXIES = ["proxy-default", "proxy-chain", "proxy-minimal"]

ISSUER = "https://accounts.google.com"
CLIENT_ID = "test-client.apps.googleusercontent.com"
SIGNING_KID = "test-key-1"


# --- Test PKI -------------------------------------------------------------------

def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _write_key(key, path):
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))


def _cert(subject_key, common_name, issuer_key=None, issuer_cert=None, dns=(), ips=()):
    now = datetime.datetime.now(datetime.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_cert.subject if issuer_cert else subject)
        .public_key(subject_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
    )
    if issuer_cert is None:
        builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    else:
        names = [x509.DNSName(n) for n in dns] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
        builder = builder.add_extension(x509.SubjectAlternativeName(names), critical=False)
    return builder.sign(issuer_key or subject_key, hashes.SHA256())


def _write_cert(cert, path):
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def generate_pki():
    """Write the CA, server certificates, and JWT signing key that compose.yaml mounts."""
    shutil.rmtree(GENERATED, ignore_errors=True)
    GENERATED.mkdir()

    ca_key = _new_key()
    ca = _cert(ca_key, "openidc-terra-proxy test CA")
    _write_cert(ca, GENERATED / "ca.pem")

    google_key = _new_key()
    google = _cert(google_key, "www.googleapis.com", ca_key, ca,
                   dns=["www.googleapis.com", "accounts.google.com", "oauth2.googleapis.com"])
    _write_cert(google, GENERATED / "google.pem")
    _write_key(google_key, GENERATED / "google-key.pem")

    proxy_key = _new_key()
    proxy = _cert(proxy_key, "localhost", ca_key, ca,
                  dns=["localhost"] + [f"{p}.test" for p in PROXIES], ips=["127.0.0.1"])
    _write_cert(proxy, GENERATED / "proxy.pem")
    _write_key(proxy_key, GENERATED / "proxy-key.pem")

    signing_key = _new_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    jwk.update(kid=SIGNING_KID, use="sig", alg="RS256")
    (GENERATED / "jwks.json").write_text(json.dumps({"keys": [jwk]}))
    return signing_key


# --- Compose stack --------------------------------------------------------------

@dataclass
class Stack:
    signing_key: rsa.RSAPrivateKey

    def compose(self, *args, check=True):
        return subprocess.run(COMPOSE + list(args), check=check, capture_output=True, text=True,
                              env={**os.environ, "PROXY_IMAGE": IMAGE})

    def url(self, service, port, scheme):
        host_port = self.compose("port", service, str(port)).stdout.strip().rsplit(":", 1)[1]
        # "localhost" rather than 127.0.0.1 so TLS verification matches the certificate.
        return f"{scheme}://localhost:{host_port}"

    def exec(self, service, *cmd):
        return self.compose("exec", "-T", service, *cmd, check=False)


def _wait_until(ready, what, timeout=90):
    deadline = time.monotonic() + timeout
    while True:
        try:
            if ready():
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f"{what} not ready after {timeout}s")
        time.sleep(0.5)


@pytest.fixture(scope="session")
def stack():
    if subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode:
        pytest.exit(f"image {IMAGE} not found; build it or set PROXY_IMAGE (see tests/README.md)", 2)
    s = Stack(signing_key=generate_pki())
    s.compose("down", "--volumes", "--remove-orphans", check=False)
    s.compose("up", "--detach")
    try:
        control = s.url("fake-google", 8080, "http")
        _wait_until(lambda: httpx.get(f"{control}/_health").is_success, "fake-google")
        for service in PROXIES:
            base = s.url(service, 443, "https")
            # The proxy is up once a request reaches the backend; /api works on every config.
            _wait_until(lambda: httpx.get(f"{base}/api/", verify=False).status_code == 401, service)
        yield s
    finally:
        (GENERATED / "compose.log").write_text(s.compose("logs", "--no-color", check=False).stdout)
        if not os.environ.get("KEEP_STACK"):
            s.compose("down", "--volumes", "--remove-orphans", check=False)


# --- Fake Google ----------------------------------------------------------------

@dataclass
class Token:
    value: str
    claims: dict


class FakeGoogle:
    def __init__(self, control_url, signing_key):
        self.control = httpx.Client(base_url=control_url)
        self.signing_key = signing_key
        self.control.post("/_reset").raise_for_status()

    def calls(self):
        return self.control.get("/_calls").raise_for_status().json()

    def tokeninfo_calls(self):
        return self.calls()["tokeninfo"]

    def access_token(self, **overrides):
        """An opaque access token that tokeninfo accepts, with Google's response fields."""
        n = uuid.uuid4().hex
        info = {
            "azp": CLIENT_ID,
            "aud": CLIENT_ID,
            "sub": str(int(n[:16], 16)),
            "scope": "openid https://www.googleapis.com/auth/userinfo.email",
            "exp": str(int(time.time()) + 3600),
            "expires_in": "3599",
            "email": f"user-{n[:8]}@example.org",
            "email_verified": "true",
            "access_type": "online",
            **overrides,
        }
        token = f"ya29.test-{n}"
        self.control.post("/_tokens", json={"token": token, "info": info}).raise_for_status()
        return Token(token, info)

    @staticmethod
    def unknown_access_token():
        return Token(f"ya29.unknown-{uuid.uuid4().hex}", {})

    def id_token(self, key=None, **overrides):
        """A Google ID token (JWT) signed with the key the fake's JWKS publishes."""
        now = int(time.time())
        n = uuid.uuid4().hex
        claims = {
            "iss": ISSUER,
            "azp": CLIENT_ID,
            "aud": CLIENT_ID,
            "sub": str(int(n[:16], 16)),
            "email": f"user-{n[:8]}@example.org",
            "email_verified": True,
            "iat": now,
            "exp": now + 3600,
            **overrides,
        }
        value = jwt.encode(claims, key or self.signing_key, algorithm="RS256",
                           headers={"kid": SIGNING_KID})
        return Token(value, claims)

    def forged_id_token(self):
        """An ID token with the right key ID but signed with a different key."""
        return self.id_token(key=_new_key())

    @contextlib.contextmanager
    def tokeninfo_unavailable(self):
        self.control.post("/_mode", json={"tokeninfo": "unavailable"}).raise_for_status()
        try:
            yield
        finally:
            self.control.post("/_mode", json={"tokeninfo": "ok"}).raise_for_status()


@pytest.fixture
def google(stack):
    return FakeGoogle(stack.url("fake-google", 8080, "http"), stack.signing_key)


# --- Proxies --------------------------------------------------------------------

class Proxy:
    def __init__(self, stack, service):
        self.stack = stack
        self.service = service
        self.client = httpx.Client(base_url=stack.url(service, 443, "https"),
                                   verify=ssl.create_default_context(cafile=GENERATED / "ca.pem"),
                                   timeout=30)

    def get(self, path, token=None, headers=None):
        headers = dict(headers or {})
        if token is not None:
            headers["Authorization"] = f"Bearer {token.value if isinstance(token, Token) else token}"
        return self.client.get(path, headers=headers)

    def introspect(self, *curl_args):
        """POST to the introspection endpoint from inside the container, as mod_oauth2 does."""
        result = self.stack.exec(self.service, "curl", "-sk", "-i", "-X", "POST", *curl_args,
                                 "https://127.0.0.1/introspect/")
        head, _, body = result.stdout.replace("\r\n", "\n").partition("\n\n")
        status_line, *header_lines = head.split("\n")
        headers = {k.strip().lower(): v.strip() for k, v in (h.split(":", 1) for h in header_lines)}
        return int(status_line.split()[1]), headers, body


def backend_headers(response):
    """The headers the echo backend received, as {lowercased name: [values]}."""
    assert response.status_code == 200, f"{response.status_code}: {response.text[:300]}"
    received = {}
    for name, value in response.json()["headers"]:
        received.setdefault(name.lower(), []).append(value)
    return received


@pytest.fixture
def proxy(stack, request):
    """Parametrize indirectly with a service name from compose.yaml."""
    return Proxy(stack, request.param)
