FROM rust:1.93-slim-bookworm AS build
WORKDIR /work
COPY server/Cargo.toml server/Cargo.lock server/
COPY server/src/ server/src/
COPY src-tauri/src/domain.rs src-tauri/src/exchange.rs src-tauri/src/retention.rs src-tauri/src/
COPY src-tauri/src/domain/ src-tauri/src/domain/
RUN cargo build --manifest-path server/Cargo.toml --release --locked

FROM debian:bookworm-slim
COPY --from=build /work/server/target/release/messenger-server /app/messenger-server
USER 1000:1000
EXPOSE 8080
CMD ["/app/messenger-server"]
