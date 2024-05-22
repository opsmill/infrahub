FROM debian:bookworm-slim
ARG TARGETPLATFORM

RUN apt-get update && \
    apt-get install -y curl libncurses5 unzip yq jq fio

COPY entrypoint.sh /entrypoint.sh

RUN bash -c 'curl -o pt_linux.zip https://www.passmark.com/downloads/pt_linux_$([ "$TARGETPLATFORM" == "linux/amd64" ] && echo "x64" || echo "arm64").zip' && \
    unzip pt_linux.zip && \
    mv PerformanceTest/pt_linux_* /usr/local/bin/pt_linux && \
    rm -rf PerformanceTest pt_linux.zip && \
    chmod +x /entrypoint.sh && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/*

CMD /entrypoint.sh
