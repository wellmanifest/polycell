# Komórki Rust są wkompilowane (include!) - podmiana pliku komórki = przebudowa tylko tego obrazu.
FROM rust:1-slim AS build
WORKDIR /app
# warstwa zależności (cache) - niezależna od komórek
COPY hosts/rust/Cargo.toml hosts/rust/Cargo.lock* hosts/rust/
RUN mkdir -p hosts/rust/src && echo "fn main(){}" > hosts/rust/src/main.rs && echo "fn main(){}" > hosts/rust/build.rs \
 && cd hosts/rust && cargo build --release 2>/dev/null || true
COPY proto proto
COPY gen/rust gen/rust
COPY cells/rust cells/rust
COPY hosts/rust hosts/rust
RUN cd hosts/rust && touch src/main.rs build.rs && cargo build --release

FROM debian:bookworm-slim
COPY --from=build /app/hosts/rust/target/release/host /usr/local/bin/host
CMD ["host"]
