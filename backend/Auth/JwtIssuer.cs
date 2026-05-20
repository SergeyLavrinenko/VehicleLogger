using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Auth;

public class JwtIssuer
{
    public string Key      { get; }
    public string Issuer   { get; }
    public string Audience { get; }
    public int    ExpireMinutes { get; }

    public JwtIssuer(IConfiguration cfg)
    {
        Key           = cfg["Jwt:Key"]      ?? throw new InvalidOperationException("Jwt:Key missing");
        Issuer        = cfg["Jwt:Issuer"]   ?? "VehicleLogger";
        Audience      = cfg["Jwt:Audience"] ?? "VehicleLogger.Api";
        ExpireMinutes = int.TryParse(cfg["Jwt:ExpireMinutes"], out var v) ? v : 1440;

        if (Encoding.UTF8.GetByteCount(Key) < 32)
            throw new InvalidOperationException("Jwt:Key must be at least 32 bytes (256 bit).");
    }

    public (string token, DateTime expiresAt) Issue(User user)
    {
        var expiresAt = DateTime.UtcNow.AddMinutes(ExpireMinutes);
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new(ClaimTypes.NameIdentifier,   user.Id.ToString()),
            new(ClaimTypes.Role,             user.Role.ToString().ToLowerInvariant()),
            new(ClaimTypes.Email,            user.Email),
            new("name",                      user.Name ?? user.Email)
        };
        if (user.TenantId is not null)
            claims.Add(new Claim("tenant_id", user.TenantId.Value.ToString()));

        var creds = new SigningCredentials(
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(Key)),
            SecurityAlgorithms.HmacSha256);

        var jwt = new JwtSecurityToken(
            issuer:   Issuer,
            audience: Audience,
            claims:   claims,
            expires:  expiresAt,
            signingCredentials: creds);

        return (new JwtSecurityTokenHandler().WriteToken(jwt), expiresAt);
    }
}
