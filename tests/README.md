# Tests

Black-box tests of the built image. They run it under docker compose next to a fake
Google (`fakes/fake_google.py`) and an echo backend (`fakes/echo.py`), and check
outcomes: status codes, what reaches the backend, and how often Google is called.

They cover what the image provides to any config: when and how tokens are verified,
the introspection endpoint's contract, the claim headers the backend receives, and
image-level behavior. Deployment-specific behavior (routing, audience allowlists) is
tested where those configs live, in terra-helmfile.

## Running

You need Docker with Compose v2 and Python 3.12 or later, plus
[uv](https://docs.astral.sh/uv/) or pip. Run the commands from the repository root.

The image only builds for x86_64 (also called amd64): its RPMs are pinned to x86_64
packages. What you need depends on your machine's CPU, which `uname -m` reports.

### x86_64 / amd64 hosts (Intel or AMD; GitHub Actions' `ubuntu-latest`)

The image runs natively:

```sh
docker build -f Dockerfile.ubi-minimal -t openidc-terra-proxy:test .
uv run --with-requirements tests/requirements.txt pytest tests
```

### arm64 / aarch64 hosts (Apple Silicon Macs, AWS Graviton, Ampere)

Build for x86_64 explicitly. Without `--platform`, Docker builds for arm64 and the
build fails at the hiredis install (`No package matches 'hiredis-...x86_64'`):

```sh
docker build --platform linux/amd64 -f Dockerfile.ubi-minimal -t openidc-terra-proxy:test .
uv run --with-requirements tests/requirements.txt pytest tests
```

The proxy containers then run under emulation; `compose.yaml` and the image tests
already request `linux/amd64`, so nothing else changes. Expect the suite to take
under a minute.

- macOS: Docker Desktop emulates x86_64 out of the box. Turning on "Use Rosetta for
  x86_64/amd64 emulation on Apple Silicon" (Settings > General) makes it faster.
- Linux: register x86_64 emulation once per boot, then check it works:

  ```sh
  docker run --privileged --rm tonistiigi/binfmt --install amd64
  docker run --rm --platform linux/amd64 registry.access.redhat.com/ubi8/ubi-minimal uname -m  # x86_64
  ```

### Options

Instead of uv, `pip install -r tests/requirements.txt && pytest tests`. To test another
image, set `PROXY_IMAGE`. Set `KEEP_STACK=1` to leave the containers running afterwards;
the containers' logs are saved to `tests/.generated/compose.log` either way.

## How it works

- `conftest.py` generates a throwaway CA, TLS certificates, and a JWT signing key in
  `.generated/`, then starts `compose.yaml`.
- The proxies trust only the test CA, and Docker network aliases point
  `www.googleapis.com` and `accounts.google.com` at the fake, so the image runs
  unmodified and never reaches the real Google.
- The proxy runs in three configurations:
  - `proxy-default`: the image's own `site.conf` and `oauth2.conf`.
  - `proxy-chain`: a mounted `oauth2.conf` (`configs/chain-oauth2.conf`) that verifies
    Google ID tokens locally before falling back to introspection.
  - `proxy-minimal`: both files replaced (`configs/minimal-site.conf`), the way
    deployments mount their own.
- Tests read the fake's call counters through its control API on port 8080.

Known gaps are marked `xfail` with the reason. `xfail_strict` is on, so when a fix
lands the test reports XPASS as a failure until its marker is removed.
