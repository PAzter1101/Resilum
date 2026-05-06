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
