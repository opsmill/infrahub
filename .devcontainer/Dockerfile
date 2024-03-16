FROM python:3.12

RUN apt-get remove -yq docker.io docker-doc docker-compose podman-docker containerd runc 2>&1 || true

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    pkg-config \
    build-essential \
    ca-certificates \
    curl \
    gnupg \
    sudo

RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
RUN chmod a+r /etc/apt/keyrings/docker.gpg
RUN echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN apt-get update && \
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

RUN useradd -m -s /bin/bash vscode && \
    # getent group docker || groupadd docker && \
    usermod -aG docker vscode && \
    newgrp docker && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /workspace

COPY . .

USER vscode

RUN pip install toml invoke

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && echo "export PATH=\"$HOME/.local/bin:$PATH\"" >> $HOME/.bashrc
