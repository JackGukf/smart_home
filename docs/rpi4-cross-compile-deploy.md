# Raspberry Pi 4 Cross-Compile and Deploy

This project can compile the C++ controller in WSL/Docker and deploy the result to a Raspberry Pi 4 over SSH.

## Recommended Workflow

Use this workflow for day-to-day development:

1. Edit code in WSL with VS Code Dev Containers.
2. Run local checks in the Docker development container.
3. Cross-compile the C++ binary for Raspberry Pi OS 64-bit.
4. Deploy the C++ binary and Python source to the Pi over SSH.

This is faster and more repeatable than manually installing every compiler tool on the Pi. The Pi still needs Python, SSH, and runtime libraries.

## Raspberry Pi Assumption

The configured cross-compiler targets:

```text
Linux aarch64 / ARM64
```

Use Raspberry Pi OS 64-bit on the Raspberry Pi 4. If you use a 32-bit OS, this toolchain will not produce the right binary.

Check the Pi:

```bash
uname -m
```

Expected result:

```text
aarch64
```

## Prepare the Raspberry Pi

On the Pi:

```bash
sudo apt update
sudo apt install -y openssh-server python3 python3-venv python3-pip rsync
sudo systemctl enable --now ssh
```

Make sure your WSL SSH key can log in:

```bash
ssh smarthome@192.168.0.176
```

The default project scripts use `smarthome@192.168.0.176`.

Quick connection check:

```bash
scripts/connect-pi.sh --check
```

## Build for Raspberry Pi 4

From WSL:

```bash
cd ~/workspace/smart-home-rpi4
./scripts/build-rpi4.sh
```

The C++ binary is created at:

```text
build/rpi4-release/src/cpp/smart_home_controller
```

You can inspect it with:

```bash
file build/rpi4-release/src/cpp/smart_home_controller
```

It should say `ARM aarch64`.

## Deploy to Raspberry Pi

From WSL:

```bash
cd ~/workspace/smart-home-rpi4
./scripts/deploy-to-pi.sh
```

The deploy script:

- Builds the Raspberry Pi C++ binary unless `--skip-build` is used.
- Copies the C++ binary to `bin/smart_home_controller`.
- Copies Python source to `src/python`.
- Copies the example device config.
- Creates or updates a Python virtual environment on the Pi.
- Installs Python requirements on the Pi.

## Run on Raspberry Pi

After deployment, SSH to the Pi:

```bash
scripts/connect-pi.sh
```

Run C++:

```bash
/home/smarthome/smart-home-rpi4/bin/smart_home_controller
```

Run Python:

```bash
/home/smarthome/smart-home-rpi4/.venv/bin/python /home/smarthome/smart-home-rpi4/src/python/controller.py
```

## Alternative: Compile Directly on the Pi

Direct Pi compilation is simpler when dependencies become complex, especially if C/C++ code links to Pi-specific system libraries. The tradeoff is slower builds.

Use this approach when:

- The project links to Raspberry Pi GPIO, camera, or vendor-specific native libraries.
- Cross-compilation dependencies become hard to mirror.
- You want the lowest setup complexity.

For this project, the best starting point is cross-compile C++ in Docker/WSL and deploy Python source. If native Pi dependencies grow later, switch that part to Pi-native builds or use a Pi-based CI runner.
