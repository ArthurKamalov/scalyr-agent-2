FROM alpine:3.18.2 as base

FROM base as full_base
RUN apk update && apk add --virtual build-dependencies \
    binutils \
    build-base \
    linux-headers \
    gcc \
    g++ \
    make \
    curl \
    python3 \
    python3-dev \
    py3-pip \
    patchelf \
    git \
    bash \
    rust \
    cargo

FROM base as prod_base
RUN apk update && apk add --no-cache python3 py3-pip
