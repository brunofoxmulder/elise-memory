ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip
WORKDIR /opt/elise-memory
COPY rootfs/ /
COPY app/ ./
RUN pip3 install --no-cache-dir --break-system-packages .
RUN chmod a+x /etc/services.d/elise-memory/run
