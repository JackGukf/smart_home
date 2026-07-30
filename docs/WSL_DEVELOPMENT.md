# WSL Development

The active development copy of this project is:

```bash
/home/jackgu/workspace/smart_home_AI
```

From Windows, the same location is:

```text
\\wsl.localhost\Ubuntu-22.04\home\jackgu\workspace\smart_home_AI
```

## Install Tools

Open Ubuntu 22.04 WSL and run:

```bash
cd ~/workspace/smart_home_AI
chmod +x scripts/install-dev-tools.sh scripts/dev-check.sh
./scripts/install-dev-tools.sh
./scripts/dev-check.sh
```

## Development Rule

Do day-to-day development inside WSL paths, not under `C:\Users\...`.

Recommended shell location:

```bash
cd ~/workspace/smart_home_AI
```

Recommended editor path:

```bash
code ~/workspace/smart_home_AI
```

## Docker-Based Development

Docker is the preferred environment for compiling and debugging this project:

```bash
cd ~/workspace/smart_home_AI
docker compose build dev
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart_home_AI
```

For the full IDE workflow, see `docs/docker-development.md`.
