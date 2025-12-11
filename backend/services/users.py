"""User service layer handling creation and credential management."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional, Tuple

import psycopg2
from psycopg2.errors import UniqueViolation

from db.connect import get_db_connection


@dataclass(frozen=True)
class CreatedUser:
    """Represents a freshly created user record."""

    id: str
    username: str
    role: str
    user_tier: str
    credit_balance: int
    is_active: bool


class UsernameAlreadyExistsError(Exception):
    """Raised when attempting to create a user with an existing username."""


class UserCreationError(Exception):
    """Raised when the user creation process fails for unexpected reasons."""


class UserLookupError(Exception):
    """Raised when user lookup operations fail."""


class UserNotFoundError(Exception):
    """Raised when a user cannot be found by username."""


def _generate_api_key() -> str:
    """Generate a secure API key returned to the caller exactly once."""

    return secrets.token_urlsafe(32)


def _hash_api_key(api_key: str) -> str:
    """Hash the API key before persisting it to the database."""

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def create_user(
    username: str, 
    email: Optional[str] = None, 
    role: str | None = None,
    user_tier: str = "junior"
) -> Tuple[CreatedUser, str]:

    api_key_plain = _generate_api_key()
    api_key_hash = _hash_api_key(api_key_plain)

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users;")
            is_first_user = cursor.fetchone()[0] == 0
            target_role = "admin" if is_first_user else (role or "member")
            # First user is always lead tier
            target_tier = "lead" if is_first_user else user_tier

            cursor.execute(
                """
                INSERT INTO users (username, email, api_key, role, user_tier, notification_email)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id::text, username, role, user_tier, credit_balance, is_active;
                """,
                (username, email, api_key_hash, target_role, target_tier, email),
            )
            record = cursor.fetchone()

        connection.commit()
    except UniqueViolation as exc:
        connection.rollback()
        raise UsernameAlreadyExistsError("Username already exists") from exc
    except psycopg2.Error as exc:
        connection.rollback()
        raise UserCreationError("Failed to create user") from exc
    finally:
        connection.close()

    if record is None:
        # No row returned should be impossible if INSERT succeeded, guard just in case.
        raise UserCreationError("User creation failed to return a record")

    created_user = CreatedUser(
        id=record[0],
        username=record[1],
        role=record[2],
        user_tier=record[3],
        credit_balance=record[4],
        is_active=record[5],
    )

    return created_user, api_key_plain


def get_user_by_api_key(api_key: str) -> Optional[CreatedUser]:
    """Retrieve an active user matching the provided API key."""

    api_key_hash = _hash_api_key(api_key)
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, username, role, user_tier, credit_balance, is_active
                FROM users
                WHERE api_key = %s;
                """,
                (api_key_hash,),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise UserLookupError("Failed to lookup user") from exc
    finally:
        connection.close()

    if record is None:
        return None

    return CreatedUser(
        id=record[0],
        username=record[1],
        role=record[2],
        user_tier=record[3],
        credit_balance=record[4],
        is_active=record[5],
    )


def get_user_by_username(username: str) -> Optional[Tuple[CreatedUser, str]]:
    """Retrieve a user by username and return their info with API key.
    
    Returns:
        Tuple of (CreatedUser, api_key_plain) or None if not found
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, username, role, user_tier, credit_balance, is_active, api_key
                FROM users
                WHERE username = %s;
                """,
                (username,),
            )
            record = cursor.fetchone()
    except psycopg2.Error as exc:
        raise UserLookupError("Failed to lookup user by username") from exc
    finally:
        connection.close()

    if record is None:
        return None

    user = CreatedUser(
        id=record[0],
        username=record[1],
        role=record[2],
        user_tier=record[3],
        credit_balance=record[4],
        is_active=record[5],
    )
    
    # Generate a new API key for this session
    api_key_plain = _generate_api_key()
    api_key_hash = _hash_api_key(api_key_plain)
    
    # Update the user's API key
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET api_key = %s
                WHERE username = %s;
                """,
                (api_key_hash, username),
            )
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        raise UserLookupError("Failed to update API key") from exc
    finally:
        connection.close()
    
    return user, api_key_plain


def get_all_admin_emails() -> List[str]:
    """Get email addresses of all active admins with notification_email set.
    
    Returns:
        List of admin email addresses
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT notification_email
                FROM users
                WHERE role = 'admin' 
                  AND is_active = TRUE 
                  AND notification_email IS NOT NULL
                  AND notification_email != '';
                """
            )
            records = cursor.fetchall()
    except psycopg2.Error as exc:
        raise UserLookupError("Failed to fetch admin emails") from exc
    finally:
        connection.close()
    
    return [record[0] for record in records]
