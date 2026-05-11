using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;

namespace VehicleLogger.Api.Endpoints;

public static class AuthEndpoints
{
    public record LoginRequest(string Email, string Password);

    public static void MapAuthEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/auth/login",   HandleLogin);
        app.MapGet ("/api/auth/context", HandleContext);
    }

    private static async Task<IResult> HandleLogin(
        LoginRequest req, AppDbContext db, JwtIssuer jwt, HttpContext ctx)
    {
        if (string.IsNullOrWhiteSpace(req.Email) || string.IsNullOrWhiteSpace(req.Password))
            return Results.BadRequest(new { error = "missing_fields" });

        var tenantCtx = ctx.GetTenantContext();
        var email = req.Email.Trim().ToLower();

        // На поддомене — пускаем только пользователя этого тенанта.
        // На apex — только super-admin (TenantId == null).
        var user = await db.Users.FirstOrDefaultAsync(u =>
            u.Email == email &&
            (tenantCtx.HasTenant
                ? u.TenantId == tenantCtx.TenantId
                : u.TenantId == null));

        if (user is null || !PasswordHasher.Verify(req.Password, user.PasswordHash))
            return Results.Json(new { error = "invalid_credentials" }, statusCode: 401);

        var (token, expiresAt) = jwt.Issue(user);
        return Results.Ok(new
        {
            token,
            expiresAt,
            user = new
            {
                id       = user.Id,
                email    = user.Email,
                name     = user.Name ?? user.Email,
                role     = user.Role.ToString().ToLowerInvariant(),
                tenantId = user.TenantId
            },
            tenant = tenantCtx.HasTenant ? new
            {
                id        = tenantCtx.Tenant!.Id,
                subdomain = tenantCtx.Tenant.Subdomain,
                name      = tenantCtx.Tenant.Name
            } : null
        });
    }

    /// Информация о текущем хосте — нужна фронту до логина (показать какой тенант).
    private static IResult HandleContext(HttpContext ctx)
    {
        var tc = ctx.GetTenantContext();
        // super-admin host = apex без поддомена (RequestedSubdomain == null И тенанта нет)
        var isSuperAdminHost = tc.RequestedSubdomain is null && !tc.HasTenant;
        return Results.Ok(new
        {
            host               = ctx.Request.Host.Host,
            isSuperAdminHost,
            tenant = tc.HasTenant ? new
            {
                id        = tc.Tenant!.Id,
                subdomain = tc.Tenant.Subdomain,
                name      = tc.Tenant.Name
            } : null,
            requestedSubdomain = tc.RequestedSubdomain
        });
    }
}
