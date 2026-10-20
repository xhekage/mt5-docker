FROM gmag11/metatrader5_vnc:latest
RUN curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq-archive.key \
    && apt-get update -qq \
    && apt-get -o Dpkg::Options::="--force-overwrite" install -y --no-install-recommends winehq-stable xdotool imagemagick \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages --no-cache-dir fastapi uvicorn websockets==15.0.1 rpyc==6.0.2
COPY config/ /opt/mt5-app/
COPY docker/init-app.sh /custom-cont-init.d/90-mt5-app
