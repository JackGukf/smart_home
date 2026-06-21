# Docker Development Environment

This project uses Docker in WSL as the repeatable development environment for C/C++ and Python work.

## Recommended IDE

Use Visual Studio Code with these extensions:

- WSL
- Dev Containers
- C/C++
- CMake Tools
- Python
- Docker

This is the best fit for Docker running inside WSL because the editor, terminal, compiler, debugger, and mounted files all agree on Linux paths.

Visual Studio 2022 can still open this folder for CMake-based C++ work because the project includes `CMakePresets.json`, but Visual Studio Code is the smoother option for mixed C/C++ plus Python plus Docker.

## Start From WSL

Open Ubuntu WSL:

```bash
cd ~/workspace/smart-home-rpi4
docker compose build dev
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart-home-rpi4
```

## Open in VS Code

From WSL:

```bash
cd ~/workspace/smart-home-rpi4
code .
```

Then choose:

```text
Dev Containers: Reopen in Container
```

VS Code will build the image from `Dockerfile`, attach to the `dev` service from `docker-compose.yml`, and use `/workspace/smart-home-rpi4` as the workspace folder.

## Build C/C++

Inside the container:

```bash
cmake --preset docker-debug
cmake --build --preset docker-debug
./build/docker-debug/src/cpp/smart_home_controller
ctest --test-dir build/docker-debug --output-on-failure
```

## Run Python

Inside the container:

```bash
python3 src/python/controller.py
python3 -m pytest
```

## Debugging

In VS Code after reopening in the container:

- Use `Debug C++ controller` to build and debug the C++ executable with GDB.
- Use `Debug Python controller` to run the Python controller with `debugpy`.

## Useful Docker Commands

```bash
docker compose build dev
docker compose run --rm dev bash
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart-home-rpi4
docker compose down
```

## Raspberry Pi 4 Cross-Compile

The Docker image also includes the ARM64 cross-compiler for Raspberry Pi OS 64-bit:

```bash
./scripts/build-rpi4.sh
```

See `docs/rpi4-cross-compile-deploy.md` for deployment over SSH.
