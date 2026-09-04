using System.ComponentModel.DataAnnotations;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Backend.Users;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;
using MongoDB.Bson;
using MongoDB.Driver;

namespace Backend.Auth;

public sealed class AuthService(
    IUserRepository users,
    IPasswordHasher<UserDocument> passwordHasher,
    IOptions<JwtOptions> jwtOptions)
{
    private const int MaxEmailLength = 320;
    private const int MaxPasswordLength = 200;
    private const int MaxDisplayNameLength = 100;

    public async Task<AuthOperationResult> RegisterAsync(
        RegisterRequest? request,
        CancellationToken cancellationToken)
    {
        var validationError = ValidateRegisterRequest(request);
        if (validationError is not null)
        {
            return AuthOperationResult.Failed(
                "invalid_input", validationError, StatusCodes.Status422UnprocessableEntity);
        }

        var email = request!.Email.Trim().ToLowerInvariant();
        var normalizedEmail = email.ToUpperInvariant();
        try
        {
            if (await users.FindByNormalizedEmailAsync(normalizedEmail, cancellationToken) is not null)
            {
                return AuthOperationResult.Failed(
                    "email_exists", "Email đã được sử dụng.", StatusCodes.Status409Conflict);
            }

            var user = new UserDocument
            {
                Id = ObjectId.GenerateNewId().ToString(),
                Email = email,
                NormalizedEmail = normalizedEmail,
                DisplayName = request.DisplayName.Trim(),
                PasswordHash = string.Empty,
                CreatedAt = DateTime.UtcNow
            };
            var passwordHash = passwordHasher.HashPassword(user, request.Password);
            user = new UserDocument
            {
                Id = user.Id,
                Email = user.Email,
                NormalizedEmail = user.NormalizedEmail,
                DisplayName = user.DisplayName,
                PasswordHash = passwordHash,
                CreatedAt = user.CreatedAt
            };

            await users.InsertAsync(user, cancellationToken);
            return new(
                User: AuthOperationResult.ToResponse(user),
                StatusCode: StatusCodes.Status201Created);
        }
        catch (MongoWriteException error) when (error.WriteError?.Code == 11000)
        {
            return AuthOperationResult.Failed(
                "email_exists", "Email đã được sử dụng.", StatusCodes.Status409Conflict);
        }
        catch (Exception error) when (
            error is MongoException or UserRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    public async Task<AuthOperationResult> LoginAsync(
        LoginRequest? request,
        CancellationToken cancellationToken)
    {
        if (request is null || string.IsNullOrWhiteSpace(request.Email)
            || string.IsNullOrEmpty(request.Password))
        {
            return AuthOperationResult.Failed(
                "invalid_input", "Email và password là bắt buộc.",
                StatusCodes.Status422UnprocessableEntity);
        }

        var email = request.Email.Trim().ToLowerInvariant();
        if (email.Length > MaxEmailLength || !new EmailAddressAttribute().IsValid(email))
        {
            return InvalidCredentials();
        }

        try
        {
            var user = await users.FindByNormalizedEmailAsync(
                email.ToUpperInvariant(), cancellationToken);
            if (user is null
                || passwordHasher.VerifyHashedPassword(
                    user, user.PasswordHash, request.Password)
                   == PasswordVerificationResult.Failed)
            {
                return InvalidCredentials();
            }

            return new(
                User: AuthOperationResult.ToResponse(user),
                AccessToken: CreateToken(user));
        }
        catch (Exception error) when (
            error is MongoException or UserRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    public async Task<AuthOperationResult> GetCurrentUserAsync(
        string? userId,
        CancellationToken cancellationToken)
    {
        if (!ObjectId.TryParse(userId, out _))
        {
            return AuthOperationResult.Failed(
                "invalid_token", "Token không hợp lệ.", StatusCodes.Status401Unauthorized);
        }

        try
        {
            var user = await users.FindByIdAsync(userId!, cancellationToken);
            return user is null
                ? AuthOperationResult.Failed(
                    "user_not_found", "Không tìm thấy người dùng.",
                    StatusCodes.Status401Unauthorized)
                : new(User: AuthOperationResult.ToResponse(user));
        }
        catch (Exception error) when (
            error is MongoException or UserRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    private string CreateToken(UserDocument user)
    {
        var options = jwtOptions.Value;
        var credentials = new SigningCredentials(
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(options.SigningKey)),
            SecurityAlgorithms.HmacSha256);
        var claims = new[]
        {
            new Claim(JwtRegisteredClaimNames.Sub, user.Id),
            new Claim(JwtRegisteredClaimNames.Email, user.Email),
            new Claim(ClaimTypes.Name, user.DisplayName)
        };
        var token = new JwtSecurityToken(
            issuer: options.Issuer,
            audience: options.Audience,
            claims: claims,
            expires: DateTime.UtcNow.AddMinutes(options.ExpiryMinutes),
            signingCredentials: credentials);
        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    private static string? ValidateRegisterRequest(RegisterRequest? request)
    {
        if (request is null) return "Yêu cầu đăng ký là bắt buộc.";

        var email = request.Email?.Trim() ?? string.Empty;
        if (email.Length == 0 || email.Length > MaxEmailLength
            || !new EmailAddressAttribute().IsValid(email))
        {
            return "Email không hợp lệ.";
        }
        if (string.IsNullOrWhiteSpace(request.Password)
            || request.Password.Length < 8 || request.Password.Length > MaxPasswordLength)
        {
            return "Password phải có từ 8 đến 200 ký tự.";
        }
        if (string.IsNullOrWhiteSpace(request.DisplayName)
            || request.DisplayName.Trim().Length > MaxDisplayNameLength)
        {
            return "displayName phải có từ 1 đến 100 ký tự.";
        }
        return null;
    }

    private static AuthOperationResult InvalidCredentials() =>
        AuthOperationResult.Failed(
            "invalid_credentials", "Email hoặc password không đúng.",
            StatusCodes.Status401Unauthorized);

    private static AuthOperationResult DatabaseFailure() =>
        AuthOperationResult.Failed(
            "database_unavailable", "Không thể kết nối đến MongoDB.",
            StatusCodes.Status503ServiceUnavailable);
}
