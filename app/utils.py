"""Utility functions for client credential management."""

import bcrypt


def hash_client_secret(plain_secret: str) -> str:
    """
    Hash a client secret.

    Args:
        plain_secret: Plain text secret

    Returns:
        str: Hashed secret
    """
    # Encode the secret to bytes and hash it
    # Bcrypt has a 72-byte limit, so we'll truncate if necessary
    secret_bytes = plain_secret.encode('utf-8')
    if len(secret_bytes) > 72:
        secret_bytes = secret_bytes[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(secret_bytes, salt)
    return hashed.decode('utf-8')

