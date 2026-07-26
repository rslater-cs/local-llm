FROM ubuntu:24.04

RUN apt update && apt install -y \
    git \
    cmake \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone https://github.com/ggerganov/llama.cpp

WORKDIR /src/llama.cpp

RUN cmake -B build \
    -DCMAKE_BUILD_TYPE=Release

RUN cmake --build build --parallel 2

WORKDIR /src/llama.cpp

ENTRYPOINT ["/src/llama.cpp/build/bin/llama-server"]