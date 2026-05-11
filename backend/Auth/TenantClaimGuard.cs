using System.Security.Claims;

namespace VehicleLogger.Api.Auth;

/// Проверяет соответствие JWT.tenant_id и текущего host-тенанта.
/// Срабатывает после Auth-middleware. Возвращает 403 если расхождение.
public class TenantClaimGuard
{
    private readonly RequestDelegate _next;
    public TenantClaimGuard(RequestDelegate next) { _next = next; }

    public async Task InvokeAsync(HttpContext ctx)
    {
        var path = ctx.Request.Path.Value ?? "";

        // Пропускаем публичные и device-эндпоинты — у них своя auth
        if (path.StartsWith("/api/auth/")    ||
            path.StartsWith("/api/health")   ||
            path.StartsWith("/api/devices/enroll")    ||
            path.StartsWith("/api/devices/provision") ||
            path.StartsWith("/api/telemetry") ||
            path.StartsWith("/api/device/ping") ||
            !path.StartsWith("/api/"))
        {
            await _next(ctx);
            return;
        }

        var tenantCtx0 = ctx.GetTenantContext();
        // Запрос пришёл на поддомен, которого нет в БД → 404, не пускаем дальше.
        if (tenantCtx0.RequestedSubdomain is not null && !tenantCtx0.HasTenant)
        {
            ctx.Response.StatusCode = 404;
            await ctx.Response.WriteAsJsonAsync(new
            {
                error              = "unknown_subdomain",
                requestedSubdomain = tenantCtx0.RequestedSubdomain
            });
            return;
        }

        if (ctx.User?.Identity?.IsAuthenticated != true)
        {
            await _next(ctx);   // [Authorize]-policy сам разрулит 401
            return;
        }

        var tenantCtx = tenantCtx0;
        var jwtTenantRaw = ctx.User.FindFirstValue("tenant_id");
        int? jwtTenantId = int.TryParse(jwtTenantRaw, out var v) ? v : null;

        // host имеет тенанта → JWT обязан иметь тот же tenant_id
        if (tenantCtx.HasTenant)
        {
            if (jwtTenantId != tenantCtx.TenantId)
            {
                ctx.Response.StatusCode = 403;
                await ctx.Response.WriteAsJsonAsync(new { error = "tenant_mismatch" });
                return;
            }
        }
        else
        {
            // apex/nip.io — только super-admin (без tenant_id в JWT)
            if (jwtTenantId is not null)
            {
                ctx.Response.StatusCode = 403;
                await ctx.Response.WriteAsJsonAsync(new { error = "use_subdomain" });
                return;
            }
        }

        await _next(ctx);
    }
}
