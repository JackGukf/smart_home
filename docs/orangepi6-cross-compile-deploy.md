# Orange Pi 6 Plus Cross-Compile and Deploy

This project compiles the C++ controller in WSL/Docker and deploys the result to
the Orange Pi 6 Plus over SSH.

## Recommended Workflow

Use this workflow for day-to-day development:

1. Edit code in WSL with VS Code Dev Containers.
2. Run local checks in the Docker development container.
3. Cross-compile the C++ binary for Ubuntu 24.04 ARM64.
4. Deploy the C++ binary and Python source to the board over SSH.

This is faster and more repeatable than installing every compiler tool on the
board. The board still needs Python, SSH, and runtime libraries.

## Target Assumptions

The configured cross-compiler targets:

```text
Linux aarch64 / ARM64
```

Check the board:

```bash
uname -m
```

Expected result:

```text
aarch64
```

### Architecture flags

The Orange Pi 6 Plus has Armv9.2-A cores (Cortex-A720 + Cortex-A520). Their
exact `-mcpu` names need GCC 14+, and the dev container ships the Ubuntu 22.04
aarch64 cross-compiler (GCC 11), so `cmake/toolchains/orangepi6-aarch64.cmake`
probes for the best `-march` the cross-compiler actually accepts and falls back
to a baseline that always runs. Pin it explicitly if you need to:

```bash
cmake --preset docker-orangepi6-release -DORANGEPI6_ARCH_FLAGS="-march=armv9-a"
```

## Prepare the Board

On the board:

```bash
sudo apt update
sudo apt install -y openssh-server python3 python3-venv python3-pip rsync
sudo systemctl enable --now ssh
```

Make sure your WSL SSH key can log in:

```bash
ssh orangepi@192.168.0.234
```

The default project scripts use `orangepi@192.168.0.234`.

Quick connection check:

```bash
scripts/connect-pi.sh --check
```

## Build

From WSL:

```bash
cd ~/workspace/smart_home_AI
./scripts/build-orangepi6.sh
```

The C++ binary is created at:

```text
build/orangepi6-release/src/cpp/smart_home_controller
```

You can inspect it with:

```bash
file build/orangepi6-release/src/cpp/smart_home_controller
```

It should say `ARM aarch64`.

## Deploy

From WSL:

```bash
cd ~/workspace/smart_home_AI
./scripts/deploy-to-pi.sh
```

The deploy script:

- Builds the ARM64 C++ binary unless `--skip-build` is used.
- Copies the C++ binary to `bin/smart_home_controller`.
- Copies Python source to `src/python`.
- Copies the example device config.
- Creates or updates a Python virtual environment on the board.
- Installs Python requirements on the board.

## Run on the Board

After deployment, SSH in:

```bash
scripts/connect-pi.sh
```

Run C++:

```bash
/home/orangepi/smart_home_AI/bin/smart_home_controller
```

Run Python:

```bash
/home/orangepi/smart_home_AI/.venv/bin/python /home/orangepi/smart_home_AI/src/python/controller.py
```

## Secondary Target: Raspberry Pi 4

The Raspberry Pi 4 is kept as a secondary target so the existing install keeps
working. Everything is the same except the board flag and the connection
details, which must be passed explicitly:

```bash
./scripts/build-orangepi6.sh --board rpi4

./scripts/deploy-to-pi.sh --board rpi4 \
    --host 192.168.0.176 --user smarthome \
    --remote-path /home/smarthome/smart-home-rpi4
```

That produces `build/rpi4-release/src/cpp/smart_home_controller` using
`cmake/toolchains/rpi4-aarch64.cmake`.

## Alternative: Compile Directly on the Board

Direct on-board compilation is simpler when dependencies become complex,
especially if C/C++ code links to board-specific system libraries. The tradeoff
is slower builds — though with 12 cores and NVMe the Orange Pi 6 Plus is a far
more viable native build host than the Pi 4 was.

Use this approach when:

- The project links to GPIO, camera, or vendor-specific native libraries.
- Cross-compilation dependencies become hard to mirror.
- You want the lowest setup complexity.

For this project, the best starting point is cross-compiling C++ in Docker/WSL
and deploying Python source. If native dependencies grow later, switch that part
to on-board builds or use an ARM64 CI runner.
