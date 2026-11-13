# Wspólny obraz Python: host-python i gateway. Konteksty ts_host/rust_host dostarcza Compose Bake.
# Gateway potrzebuje wszystkich trzech runtime'ów do lokalnego transportu stdio.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 POLYCELL_ROOT=/app
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY proto proto
COPY contracts contracts
COPY tools tools
COPY gen gen
COPY tests tests
COPY cells/python cells/python
COPY hosts/python hosts/python
COPY --from=ts_host /usr/local/bin/node /usr/local/bin/node
COPY --from=ts_host /app/hosts/ts hosts/ts
COPY --from=ts_host /app/cells/ts cells/ts
COPY --from=rust_host /usr/local/bin/host hosts/rust/target/release/host
COPY gateway gateway
RUN python -m grpc_tools.protoc -Iproto --python_out=gen/python --grpc_python_out=gen/python proto/polycell/v1/cellhost.proto
CMD ["python", "hosts/python/host.py"]
