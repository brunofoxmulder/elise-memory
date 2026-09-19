FROM ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.24

ARG BUILD_VERSION
ARG BUILD_ARCH

WORKDIR /opt/elise-memory
COPY rootfs/ /
COPY app/ ./
RUN pip3 install --no-cache-dir --break-system-packages .
RUN chmod a+x \
    /etc/services.d/elise-memory/run \
    /etc/services.d/elise-memory/discovery

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.title="Élise Memory" \
      org.opencontainers.image.description="Local deterministic memory for Home Assistant"
