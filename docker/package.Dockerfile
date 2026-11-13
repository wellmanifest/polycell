# Shared evaluator/compiler image; never stored inside a one-cell Git package.
FROM rust:1-slim AS compiler
FROM node:22-slim AS node
FROM python:3.12-slim
ENV CARGO_HOME=/usr/local/cargo RUSTUP_HOME=/usr/local/rustup
ENV PATH=/usr/local/cargo/bin:$PATH
COPY --from=compiler /usr/local/cargo /usr/local/cargo
COPY --from=compiler /usr/local/rustup /usr/local/rustup
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=forge_wheels heyasa_forge_base-0.3.0-py3-none-any.whl /tmp/heyasa_forge_base-0.3.0-py3-none-any.whl
RUN echo 'cd402a81e819ba8550420955ee97842b63cbd72d4a37410a540eadc0421e5ba2  /tmp/heyasa_forge_base-0.3.0-py3-none-any.whl' | sha256sum -c - \
 && pip install --no-cache-dir --no-deps /tmp/heyasa_forge_base-0.3.0-py3-none-any.whl
# Keep Rust's dependency cache independent of Python/TS prompts and package tooling.
COPY hosts/rust hosts/rust
COPY proto proto
COPY gen/rust gen/rust
COPY cells/rust cells/rust
RUN cd hosts/rust && cargo build --release --locked \
 && chmod -R a+rX /usr/local/cargo /usr/local/rustup /app/hosts/rust/target
COPY hosts/ts/package.json hosts/ts/package-lock.json hosts/ts/
RUN cd hosts/ts && npm ci --omit=dev
COPY tools tools
COPY standard standard
COPY gateway gateway
COPY hosts/python hosts/python
COPY hosts/ts/host.ts hosts/ts/host.ts
COPY cells cells
COPY contracts contracts
COPY gen gen
COPY tests tests
RUN python tools/polycell/gen.py \
 && python -m grpc_tools.protoc -Iproto --python_out=gen/python --grpc_python_out=gen/python proto/polycell/v1/cellhost.proto
CMD ["python", "tools/polycell/package_worker.py"]
