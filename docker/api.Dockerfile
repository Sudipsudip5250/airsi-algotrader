FROM node:20-alpine

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY lib/ ./lib/
COPY artifacts/api-server/ ./artifacts/api-server/

RUN npm install -g pnpm && pnpm install --frozen-lockfile

WORKDIR /app/artifacts/api-server
RUN pnpm run build

EXPOSE 5000
CMD ["node", "--enable-source-maps", "./dist/index.mjs"]
