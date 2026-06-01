# ============ build stage ============
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Сначала только .csproj — слой restore кэшируется,
# пока не меняются зависимости.
COPY VehicleLogger.Api.csproj ./
RUN dotnet restore VehicleLogger.Api.csproj

# Остальной код + публикация
COPY . ./
RUN dotnet publish VehicleLogger.Api.csproj -c Release -o /app/publish --no-restore

# ============ runtime stage ============
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app

# curl нужен только для HEALTHCHECK ниже
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/publish ./

# Каталог под файл SQLite — сюда docker-compose монтирует volume,
# чтобы БД переживала пересборку образа.
RUN mkdir -p /app/data

# Kestrel слушает 8080 внутри контейнера
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

# Бэкенд сам поднимает /api/health — используем его как healthcheck
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fsS http://localhost:8080/api/health || exit 1

ENTRYPOINT ["dotnet", "VehicleLogger.Api.dll"]
