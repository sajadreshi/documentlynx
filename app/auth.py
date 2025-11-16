"""Authentication dependencies and utilities."""

import logging
import bcrypt
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ClientCredential

logger = logging.getLogger(__name__)


def verify_client_secret(plain_secret: str, hashed_secret: str) -> bool:
    """
    Verify client secret against hashed secret.

    Args:
        plain_secret: Plain text secret
        hashed_secret: Hashed secret from database

    Returns:
        bool: True if secret matches, False otherwise
    """
    try:
        # Encode the secret to bytes and truncate if necessary (bcrypt 72-byte limit)
        secret_bytes = plain_secret.encode('utf-8')
        if len(secret_bytes) > 72:
            secret_bytes = secret_bytes[:72]
        
        # Verify the secret
        return bcrypt.checkpw(secret_bytes, hashed_secret.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying client secret: {str(e)}")
        return False


async def authenticate_client(
    client_id: str = Header(..., alias="X-Client-Id", description="Client ID for authentication"),
    client_secret: str = Header(..., alias="X-Client-Secret", description="Client secret for authentication"),
    db: Session = Depends(get_db)
) -> ClientCredential:
    """
    Authenticate client using client_id and client_secret.

    Args:
        client_id: Client ID from header
        client_secret: Client secret from header
        db: Database session

    Returns:
        ClientCredential: Authenticated client credential object

    Raises:
        HTTPException: If authentication fails
    """
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client ID and Client Secret are required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query database for client credential
    client = db.query(ClientCredential).filter(
        ClientCredential.client_id == client_id,
        ClientCredential.is_active == True
    ).first()

    if not client:
        logger.warning(f"Authentication failed: Client ID not found or inactive: {client_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify client secret
    if not verify_client_secret(client_secret, client.client_secret):
        logger.warning(f"Authentication failed: Invalid secret for client: {client_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"Client authenticated successfully: {client_id}")
    return client

