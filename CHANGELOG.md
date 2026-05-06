# [0.2.0](https://github.com/PAzter1101/Resilum/compare/v0.1.1...v0.2.0) (2026-05-06)


### Bug Fixes

* **bridge/pump:** TLS handshake breaks through SOCKS-egress + ship local check.sh ([a139377](https://github.com/PAzter1101/Resilum/commit/a13937754f95daa1a2f8c23cfed8e097429e2387))
* **entrypoint, deps:** rnsd-first startup, network identity, optional daemons ([3204b33](https://github.com/PAzter1101/Resilum/commit/3204b33259ecdcc3420808cb04a636bea4ba2e94))


### Features

* **bridge:** event-driven re-announce + 10-min interval + strict warnings ([a8ad9b7](https://github.com/PAzter1101/Resilum/commit/a8ad9b76bc05b2df4c3d1d28bfcf79d5f7cd3ede)), closes [#18](https://github.com/PAzter1101/Resilum/issues/18) [#19](https://github.com/PAzter1101/Resilum/issues/19) [#18](https://github.com/PAzter1101/Resilum/issues/18)
* **bridge:** SOCKS-egress over mesh — symmetric public-IP exit between peers ([d72eb9e](https://github.com/PAzter1101/Resilum/commit/d72eb9efb48d37570296051ab0e84311c238c049)), closes [#17](https://github.com/PAzter1101/Resilum/issues/17) [#16](https://github.com/PAzter1101/Resilum/issues/16)
* **rns:** I2P bidirectional via i2pd, plus check.sh local-build fix ([6ab5c06](https://github.com/PAzter1101/Resilum/commit/6ab5c0661004b5fba71c378d8e6d1b4a15df0585)), closes [#18](https://github.com/PAzter1101/Resilum/issues/18)
* **rns:** interface-discovery + replace dead bootstraps with live mesh anchors ([47ac8ed](https://github.com/PAzter1101/Resilum/commit/47ac8ed2ff5ce8d04f8454f5e019d4267f9b5ceb))
* **rns:** SOCKS5-aware TCPClientInterface for discovered .onion peers ([0f43106](https://github.com/PAzter1101/Resilum/commit/0f4310618d56e73d6cc430f31e60dd3f52113a3d))
* **supervisor:** env-var expansion + auto-discover connect target with skip-self ([e1e3ff6](https://github.com/PAzter1101/Resilum/commit/e1e3ff64c99714d9d9be6e7bc2fa1fb0f2a88616))

## Docker Images

Multi-arch images (`linux/amd64`, `linux/arm64`) published to **GitHub Container Registry** and **Docker Hub**:

| Profile | GHCR | Docker Hub |
|---|---|---|
| `full` *(default, `latest` alias)* | `ghcr.io/pazter1101/resilum:full-0.2.0` | `pazter1101/resilum:full-0.2.0` |
| `covert` (Tor + obfs4 + email/ICMP/DNS) | `ghcr.io/pazter1101/resilum:covert-0.2.0` | `pazter1101/resilum:covert-0.2.0` |
| `mesh` (Yggdrasil + I2P) | `ghcr.io/pazter1101/resilum:mesh-0.2.0` | `pazter1101/resilum:mesh-0.2.0` |
| `lora` (Reticulum + LoRa only) | `ghcr.io/pazter1101/resilum:lora-0.2.0` | `pazter1101/resilum:lora-0.2.0` |

### Usage
```bash
docker compose --profile headless up
```

## [0.1.1](https://github.com/PAzter1101/Resilum/compare/v0.1.0...v0.1.1) (2026-05-06)


### Bug Fixes

* **ci:** drop linux/arm/v7 from multi-arch buildx targets ([d1a40ae](https://github.com/PAzter1101/Resilum/commit/d1a40ae00c0178d2b93509c0ed2d591afdaa2387))

## Docker Images

Multi-arch images (`linux/amd64`, `linux/arm64`) published to **GitHub Container Registry** and **Docker Hub**:

| Profile | GHCR | Docker Hub |
|---|---|---|
| `full` *(default, `latest` alias)* | `ghcr.io/pazter1101/resilum:full-0.1.1` | `pazter1101/resilum:full-0.1.1` |
| `covert` (Tor + obfs4 + email/ICMP/DNS) | `ghcr.io/pazter1101/resilum:covert-0.1.1` | `pazter1101/resilum:covert-0.1.1` |
| `mesh` (Yggdrasil + I2P) | `ghcr.io/pazter1101/resilum:mesh-0.1.1` | `pazter1101/resilum:mesh-0.1.1` |
| `lora` (Reticulum + LoRa only) | `ghcr.io/pazter1101/resilum:lora-0.1.1` | `pazter1101/resilum:lora-0.1.1` |

### Usage
```bash
docker compose --profile headless up
```

# [0.1.0](https://github.com/PAzter1101/Resilum/compare/v0.0.0...v0.1.0) (2026-05-06)


### Features

* **ci:** add CI/CD, code-quality, dependabot pipelines ([3186321](https://github.com/PAzter1101/Resilum/commit/3186321206aec86a2b46ef6b14ff9e2153083b6d))

## Docker Images

Multi-arch images (`linux/amd64`, `linux/arm64`, `linux/arm/v7`) published to **GitHub Container Registry** and **Docker Hub**:

| Profile | GHCR | Docker Hub |
|---|---|---|
| `full` *(default, `latest` alias)* | `ghcr.io/pazter1101/resilum:full-0.1.0` | `pazter1101/resilum:full-0.1.0` |
| `covert` (Tor + obfs4 + email/ICMP/DNS) | `ghcr.io/pazter1101/resilum:covert-0.1.0` | `pazter1101/resilum:covert-0.1.0` |
| `mesh` (Yggdrasil + I2P) | `ghcr.io/pazter1101/resilum:mesh-0.1.0` | `pazter1101/resilum:mesh-0.1.0` |
| `lora` (Reticulum + LoRa only) | `ghcr.io/pazter1101/resilum:lora-0.1.0` | `pazter1101/resilum:lora-0.1.0` |

### Usage
```bash
docker compose --profile headless up
```
