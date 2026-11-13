# Postgres bez demona systemowego: PGlite (WASM) w procesie Node + protokół wire PG.
FROM node:22-slim
WORKDIR /db
COPY db/pglite/package.json db/pglite/package-lock.json ./
RUN npm ci --omit=dev
COPY db/pglite/server.mjs ./
ENV PGLITE_DATA=/data PGPORT=5432
VOLUME /data
CMD ["node", "server.mjs"]
