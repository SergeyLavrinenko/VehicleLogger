using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Auth;

/// Резолв тенанта по Host-заголовку. Кэшируется на время запроса в HttpContext.Items.
///
/// Правила:
///   acme.nonconf.ru     → ищем Tenant с subdomain=acme. Нет → 404 unknown_subdomain.
///   nonconf.ru          → no-tenant (глобальный режим, тестирование/super-admin).
///   91.188.212.119.nip.io → no-tenant (legacy для симулятора и старых тестов).
///   localhost / IP      → no-tenant.
public class TenantContext
{
    public Tenant? Tenant { get; }
    public string? RequestedSubdomain { get; }

    public bool HasTenant => Tenant is not null;
    public int?  TenantId => Tenant?.Id;

    public TenantContext(Tenant? tenant, string? requestedSubdomain)
    {
        Tenant = tenant;
        RequestedSubdomain = requestedSubdomain;
    }
}

public static class TenantResolver
{
    private const string ApexBaseDomain   = "nonconf.ru";
    private const string LegacyNipDomain  = "91.188.212.119.nip.io";

    private static readonly Regex SubdomainRegex =
        new("^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$", RegexOptions.Compiled);

    public static async Task<TenantContext> ResolveAsync(HttpContext ctx, AppDbContext db)
    {
        var host = (ctx.Request.Host.Host ?? "").ToLowerInvariant();
        var sub  = ExtractSubdomain(host);

        if (sub is null)
            return new TenantContext(null, null);

        var tenant = await db.Tenants.FirstOrDefaultAsync(t => t.Subdomain == sub);
        return new TenantContext(tenant, sub);
    }

    /// Возвращает поддомен, либо null если запрос идёт на apex / nip.io / IP / localhost.
    public static string? ExtractSubdomain(string host)
    {
        if (string.IsNullOrEmpty(host)) return null;
        if (host == ApexBaseDomain) return null;
        if (host == LegacyNipDomain) return null;
        if (IsIpOrLocal(host)) return null;

        if (host.EndsWith("." + ApexBaseDomain, StringComparison.Ordinal))
        {
            var sub = host[..^("." + ApexBaseDomain).Length];
            // Поддомен может быть составным (a.b.nonconf.ru) — берём только первую часть как идентификатор
            // и валидируем по RFC 1035.
            var firstLabel = sub.Split('.', 2)[0];
            return SubdomainRegex.IsMatch(firstLabel) ? firstLabel : null;
        }
        return null;
    }

    private static bool IsIpOrLocal(string host) =>
        host == "localhost" ||
        System.Net.IPAddress.TryParse(host, out _);
}

/// Middleware: на каждом запросе считает Tenant и кладёт в HttpContext.Items.
public class TenantMiddleware
{
    public const string ItemKey = "TenantContext";
    private readonly RequestDelegate _next;
    public TenantMiddleware(RequestDelegate next) { _next = next; }

    public async Task InvokeAsync(HttpContext ctx, AppDbContext db)
    {
        ctx.Items[ItemKey] = await TenantResolver.ResolveAsync(ctx, db);
        await _next(ctx);
    }
}

public static class TenantHttpContextExtensions
{
    public static TenantContext GetTenantContext(this HttpContext ctx)
        => ctx.Items.TryGetValue(TenantMiddleware.ItemKey, out var v) && v is TenantContext tc
            ? tc
            : new TenantContext(null, null);
}
