FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

ARG USERNAME=developer
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN dpkg --add-architecture arm64

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
        libcurl4-openssl-dev:arm64 \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        rsync \
        openssh-client \
        sudo \
        vim \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}" -s /bin/bash \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
    && chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspace/smart-home-rpi4

COPY src/python/requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && if [ -s /tmp/requirements.txt ]; then python3 -m pip install --no-cache-dir -r /tmp/requirements.txt; fi

USER ${USERNAME}

CMD ["/bin/bash"]
