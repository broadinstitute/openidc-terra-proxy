"""What the image guarantees to whatever config a deployment mounts over it."""

import subprocess
import time

import pytest
from conftest import IMAGE

PLATFORM = ["--platform", "linux/amd64"]


@pytest.mark.parametrize("proxy", ["proxy-minimal"], indirect=True)
def test_introspection_survives_a_replaced_site_conf(proxy, google):
    assert proxy.get("/api/x", google.access_token()).status_code == 200


@pytest.mark.parametrize("proxy", ["proxy-minimal"], indirect=True)
def test_id_tokens_work_with_a_replaced_site_conf(proxy, google):
    # Shows the mounted config itself is sound, so the xfail above is about introspection.
    assert proxy.get("/api/x", google.id_token()).status_code == 200


@pytest.mark.parametrize("proxy", ["proxy-default"], indirect=True)
def test_introspection_is_not_reachable_from_outside(proxy, google):
    token = google.access_token()
    response = proxy.client.post("/introspect/", data={"token": token.value})
    assert response.status_code in (403, 404)
    assert google.tokeninfo_calls() == 0


@pytest.mark.parametrize("proxy", ["proxy-default"], indirect=True)
def test_responses_do_not_advertise_versions(proxy):
    # A response httpd generates itself; proxied ones carry the backend's Server header.
    response = proxy.get("/api/x")
    assert response.status_code == 401
    assert response.headers["server"] == "Apache"
    assert "x-powered-by" not in response.headers


def test_required_modules_are_loaded():
    result = subprocess.run(
        ["docker", "run", "--rm", *PLATFORM, IMAGE, "/usr/bin/run-httpd", "-M"],
        capture_output=True,
        text=True,
        check=True,
    )
    modules = {
        line.split()[0] for line in result.stdout.splitlines() if line.startswith(" ")
    }
    required = {
        "oauth2_module",
        "ssl_module",
        "headers_module",
        "rewrite_module",
        "proxy_module",
        "proxy_http_module",
        "authz_core_module",
    }
    assert required <= modules, f"missing {required - modules}"


def test_stops_gracefully():
    container = subprocess.run(
        ["docker", "run", "--detach", *PLATFORM, IMAGE],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        # Wait until httpd answers: a stop signal sent before it installs its handlers is lost.
        deadline = time.monotonic() + 60
        while subprocess.run(
            [
                "docker",
                "exec",
                container,
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "http://127.0.0.1/",
            ],
            capture_output=True,
        ).returncode:
            assert time.monotonic() < deadline, "httpd never started"
            time.sleep(0.5)
        subprocess.run(
            ["docker", "stop", "--time", "10", container],
            capture_output=True,
            check=True,
        )
        exit_code = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.ExitCode}}", container],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert exit_code == "0"
    finally:
        subprocess.run(["docker", "rm", "--force", container], capture_output=True)
