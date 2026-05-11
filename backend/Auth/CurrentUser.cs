using System.Security.Claims;

namespace VehicleLogger.Api.Auth;

public static class CurrentUser
{
    /// tenant_id из JWT-токена (null = super-admin)
    public static int? GetTenantId(this ClaimsPrincipal user)
    {
        var raw = user.FindFirstValue("tenant_id");
        return int.TryParse(raw, out var v) ? v : null;
    }

    public static int? GetUserId(this ClaimsPrincipal user)
    {
        var raw = user.FindFirstValue(ClaimTypes.NameIdentifier);
        return int.TryParse(raw, out var v) ? v : null;
    }
}
