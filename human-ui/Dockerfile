FROM node:24-alpine
WORKDIR /app
COPY --chown=node:node server.mjs index.html favicon.svg package.json ./
COPY --chown=node:node src ./src
COPY --chown=node:node assets ./assets
USER node
ENV HOST=0.0.0.0 PORT=5173 GAME_API_URL=http://boardgame-api:8000
EXPOSE 5173
CMD ["node", "server.mjs"]
