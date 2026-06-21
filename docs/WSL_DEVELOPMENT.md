# WSL Development

The active development copy of this project is:

```bash
/home/jackgu/workspace/smart-home-rpi4
```

From Windows, the same location is:

```text
\\wsl.localhost\Ubuntu-22.04\home\jackgu\workspace\smart-home-rpi4
```

## Install Tools

Open Ubuntu 22.04 WSL and run:

```bash
cd ~/workspace/smart-home-rpi4
chmod +x scripts/install-dev-tools.sh scripts/dev-check.sh
./scripts/install-dev-tools.sh
./scripts/dev-check.sh
```

## Development Rule

Do day-to-day development inside WSL paths, not under `C:\Users\...`.

Recommended shell location:

```bash
cd ~/workspace/smart-home-rpi4
```

Recommended editor path:

```bash
code ~/workspace/smart-home-rpi4
```

## Docker-Based Development

Docker is the preferred environment for compiling and debugging this project:

```bash
cd ~/workspace/smart-home-rpi4
docker compose build dev
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart-home-rpi4
```

For the full IDE workflow, see `docs/docker-development.md`.
