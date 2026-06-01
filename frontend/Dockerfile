# ============ build stage ============
FROM node:20-alpine AS build
WORKDIR /app

# npm ci — детерминированная установка по package-lock.json
COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build

# ============ runtime stage ============
FROM nginx:1.27-alpine AS runtime

# Свой конфиг: SPA-fallback + проксирование /api на бэкенд
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Статика собранного Vite-приложения
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
