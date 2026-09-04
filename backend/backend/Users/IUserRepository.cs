namespace Backend.Users;

public interface IUserRepository
{
    Task InsertAsync(UserDocument user, CancellationToken cancellationToken);

    Task<UserDocument?> FindByNormalizedEmailAsync(
        string normalizedEmail,
        CancellationToken cancellationToken);

    Task<UserDocument?> FindByIdAsync(string id, CancellationToken cancellationToken);
}

public sealed class UserRepositoryUnavailableException : Exception
{
    public UserRepositoryUnavailableException()
        : base("User persistence is not configured.")
    {
    }
}

public sealed class UnavailableUserRepository : IUserRepository
{
    public Task InsertAsync(UserDocument user, CancellationToken cancellationToken) => Failed();

    public Task<UserDocument?> FindByNormalizedEmailAsync(
        string normalizedEmail,
        CancellationToken cancellationToken) => Failed<UserDocument?>();

    public Task<UserDocument?> FindByIdAsync(
        string id,
        CancellationToken cancellationToken) => Failed<UserDocument?>();

    private static Task<T> Failed<T>() =>
        Task.FromException<T>(new UserRepositoryUnavailableException());

    private static Task Failed() =>
        Task.FromException(new UserRepositoryUnavailableException());
}
