using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Endpoints;
using VehicleLogger.Api.Services;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("Default")
    ?? "Data Source=vehiclelogger.db";

builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite(connectionString));

builder.Services.AddSingleton<JwtIssuer>();
builder.Services.AddHttpClient<OllamaClient>();

var jwtKey      = builder.Configuration["Jwt:Key"]      ?? "";
var jwtIssuer   = builder.Configuration["Jwt:Issuer"]   ?? "VehicleLogger";
var jwtAudience = builder.Configuration["Jwt:Audience"] ?? "VehicleLogger.Api";

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(opt =>
    {
        opt.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer           = true,
            ValidateAudience         = true,
            ValidateLifetime         = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer              = jwtIssuer,
            ValidAudience            = jwtAudience,
            IssuerSigningKey         = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey)),
            ClockSkew                = TimeSpan.FromMinutes(2)
        };
    });

builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("admin",  p => p.RequireRole("admin"));
    options.AddPolicy("driver", p => p.RequireRole("driver"));
});

builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .AllowAnyOrigin()
    .AllowAnyHeader()
    .AllowAnyMethod()));

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await db.Database.EnsureCreatedAsync();
    await SchemaUpdater.UpdateAsync(db);
    await DbSeeder.SeedAsync(db);
}

app.UseForwardedHeaders(new ForwardedHeadersOptions
{
    ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto,
    KnownNetworks = { },
    KnownProxies  = { }
});

app.UseCors();
app.UseMiddleware<VehicleLogger.Api.Auth.TenantMiddleware>();
app.UseAuthentication();
app.UseAuthorization();
app.UseMiddleware<VehicleLogger.Api.Auth.TenantClaimGuard>();

app.MapGet("/api/health", () => Results.Ok(new
{
    service = "VehicleLogger.Api",
    time = DateTime.UtcNow
}));

app.MapDeviceEndpoints();
app.MapVehicleEndpoints();
app.MapAuthEndpoints();
app.MapProvisioningEndpoints();
app.MapDeviceListEndpoints();
app.MapEnrollmentEndpoints();
app.MapTenantEndpoints();
app.MapAiSummaryEndpoints();
app.MapDriverEndpoints();

app.Run();
