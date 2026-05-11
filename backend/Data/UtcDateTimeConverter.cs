using Microsoft.EntityFrameworkCore.Storage.ValueConversion;

namespace VehicleLogger.Api.Data;

/// При записи: приводим к UTC. При чтении: помечаем Kind = Utc
/// (SQLite не сохраняет Kind, без этого .NET считает значение Unspecified
/// и сериализует JSON без 'Z' → JS парсит как локальное время → баг).
public class UtcDateTimeConverter : ValueConverter<DateTime, DateTime>
{
    public UtcDateTimeConverter() : base(
        v => v.Kind == DateTimeKind.Utc ? v : v.ToUniversalTime(),
        v => DateTime.SpecifyKind(v, DateTimeKind.Utc))
    { }
}

public class UtcNullableDateTimeConverter : ValueConverter<DateTime?, DateTime?>
{
    public UtcNullableDateTimeConverter() : base(
        v => v.HasValue ? (v.Value.Kind == DateTimeKind.Utc ? v.Value : v.Value.ToUniversalTime()) : v,
        v => v.HasValue ? DateTime.SpecifyKind(v.Value, DateTimeKind.Utc) : v)
    { }
}
