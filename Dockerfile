FROM ghcr.io/home-assistant/base:3.23

ARG BUILD_VERSION
ARG BUILD_ARCH

RUN apk add --no-cache python3 py3-pip
COPY . /app
WORKDIR /app
RUN pip3 install --no-cache-dir --break-system-packages .
COPY run.sh /run.sh
RUN chmod 0755 /run.sh
ENV PYTHONPATH=/app

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.title="Élise Memory" \
      org.opencontainers.image.description="Local deterministic memory for Maison Cognitive"

CMD ["/run.sh"]
