FROM node:20-alpine
WORKDIR /app

# sim.js — единственный файл, внешних зависимостей нет (использует встроенный fetch)
COPY sim.js ./

# Флаги (--url, --interval, --device, --key) передаются из docker-compose
ENTRYPOINT ["node", "sim.js"]
