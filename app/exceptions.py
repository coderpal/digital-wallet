"""
Custom Exception Classes
------------------------
Centralised exception definitions for the entire application.

Why custom exceptions instead of raising HTTPException directly in routes?
- Consistency: every error response has the same structure regardless of
  where in the codebase it originates.
- Reusability: the same exception can be raised from a service, a helper,
  or a route handler without duplicating status codes and messages.
- Readability: raise UserNotFoundException() is self-documenting;
  raise HTTPException(status_code=404, detail="User not found") is not.
- Testability: tests can assert on specific exception types, not magic strings.

All exceptions inherit from WalletException which itself inherits from
FastAPI's HTTPException, so FastAPI handles them automatically and returns
the correct HTTP status code and JSON body.
"""

from fastapi import HTTPException, status


class WalletException(HTTPException):
    """
    Base exception for all application-specific errors.
    Inherits from HTTPException so FastAPI serialises it automatically
    into a JSON response with the correct HTTP status code.
    All domain exceptions should inherit from this class.
    """
    pass


class UserNotFoundException(WalletException):
    """
    Raised when a requested user does not exist in the database.
    Used in profile lookups, transfer targets, and admin operations.
    Returns HTTP 404 Not Found.
    """
    def __init__(self, identifier: str = ""):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {identifier}" if identifier else "User not found"
        )


class UserAlreadyExistsException(WalletException):
    """
    Raised during registration when the email is already registered.
    Returns HTTP 409 Conflict — the resource already exists.
    Using 409 instead of 400 gives the client precise information
    to display a "this email is already in use" message.
    """
    def __init__(self, email: str = ""):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email {email} already exists"
        )


class InvalidCredentialsException(WalletException):
    """
    Raised when login credentials are incorrect (wrong email or password).
    Returns HTTP 401 Unauthorized.

    Intentionally vague in the detail message — "Invalid email or password"
    rather than "Email not found" or "Wrong password". This prevents
    user enumeration attacks where an attacker probes which emails are registered.

    WWW-Authenticate header is included as required by the HTTP spec
    for 401 responses on Bearer token APIs.
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )


class InsufficientBalanceException(WalletException):
    """
    Raised when a transfer is attempted but the sender's wallet
    does not have enough balance to cover the transfer amount.
    Returns HTTP 400 Bad Request — the request itself is valid but
    the business rule (sufficient funds) is not satisfied.
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient wallet balance to complete this transaction"
        )


class InvalidTokenException(WalletException):
    """
    Raised when a JWT token cannot be validated — expired, malformed,
    tampered with, or signed with a different key.
    Returns HTTP 401 Unauthorized.
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials. Token may be expired or invalid.",
            headers={"WWW-Authenticate": "Bearer"}
        )


class SelfTransferException(WalletException):
    """
    Raised when a user attempts to transfer money to their own wallet.
    Returns HTTP 400 Bad Request.
    This is a business rule violation — self-transfers serve no purpose
    and could be used to manipulate transaction history.
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot transfer funds to your own wallet"
        )


class TransactionNotFoundException(WalletException):
    """
    Raised when a requested transaction record does not exist,
    or when a user attempts to access a transaction that belongs
    to a different user (we return 404 instead of 403 to avoid
    confirming the transaction exists at all — security best practice).
    Returns HTTP 404 Not Found.
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )