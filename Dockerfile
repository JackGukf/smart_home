FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

ARG USERNAME=developer
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

# Configure apt sources: pin amd64/i386 to archive.ubuntu.com, arm64 to ports.ubuntu.com
RUN dpkg --add-architecture arm64 \
    && echo 'deb [arch=amd64,i386] http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse' > /etc/apt/sources.list \
    && echo 'deb [arch=amd64,i386] http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse' >> /etc/apt/sources.list \
    && echo 'deb [arch=amd64,i386] http://archive.ubuntu.com/ubuntu jammy-security main restricted universe multiverse' >> /etc/apt/sources.list \
    && echo 'deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy main restricted universe multiverse' >> /etc/apt/sources.list \
    && echo 'deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-updates main restricted universe multiverse' >> /etc/apt/sources.list \
    && echo 'deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-security main restricted universe multiverse' >> /etc/apt/sources.list

# Install amd64 host tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash-completion \
        build-essential \
        ca-certificates \
        clang \
        clang-format \
        clang-tidy \
        cmake \
        curl \
        file \
        g++-aarch64-linux-gnu \
        gcc-aarch64-linux-gnu \
        gdb \
        gdb-multiarch \
        git \
        iproute2 \
        iputils-ping \
        less \
        libgtest-dev \
        mosquitto-clients \
        nano \
        ninja-build \
        libssl-dev \
        libdbus-1-dev \
        libglib2.0-dev \
        libavahi-client-dev \
        libreadline-dev \
        libgirepository1.0-dev \
        libcairo2-dev \
        nlohmann-json3-dev \
        unzip \
        libcurl4-openssl-dev \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        python-is-python3 \
        rsync \
        openssh-client \
        sudo \
        vim \
    && rm -rf /var/lib/apt/lists/*

# Install arm64 cross-compile target libraries.
# libcurl4-openssl-dev:arm64 conflicts with its amd64 counterpart when both are
# installed; use the runtime lib only and create the linker symlink manually.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libssl-dev:arm64 \
        libcurl4:arm64 \
        libavahi-client-dev:arm64 \
        libglib2.0-dev:arm64 \
        libdbus-1-dev:arm64 \
    && ln -sf /usr/lib/aarch64-linux-gnu/libcurl.so.4 /usr/lib/aarch64-linux-gnu/libcurl.so \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}" -s /bin/bash \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
    && chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspace/smart-home-rpi4

COPY src/python/requirements.txt /tmp/requirements.txt
# Matter CHIP SDK build tools: IDL codegen (lark, jinja2, stringcase) and matter_idl package
COPY third_party/connectedhomeip/scripts/setup/requirements.build.txt /tmp/requirements.build.txt
COPY third_party/connectedhomeip/scripts/py_matter_idl /tmp/py_matter_idl
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && if [ -s /tmp/requirements.txt ]; then python3 -m pip install --no-cache-dir -r /tmp/requirements.txt; fi \
    && python3 -m pip install --no-cache-dir -r /tmp/requirements.build.txt \
    && python3 -m pip install --no-cache-dir /tmp/py_matter_idl

USER ${USERNAME}

CMD ["/bin/bash"]
