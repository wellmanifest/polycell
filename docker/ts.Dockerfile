FROM node:22-slim
ENV POLYCELL_ROOT=/app NODE_NO_WARNINGS=1
WORKDIR /app/hosts/ts
COPY hosts/ts/package.json hosts/ts/package-lock.json ./
RUN npm ci --omit=dev
WORKDIR /app
COPY proto proto
COPY gen gen
COPY cells/ts cells/ts
COPY hosts/ts/host.ts hosts/ts/host.ts
COPY twin twin
CMD ["node", "--experimental-strip-types", "hosts/ts/host.ts"]
