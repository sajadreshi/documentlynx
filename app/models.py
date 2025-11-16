"""Database models."""

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class ClientCredential(Base):
    """Model for client credentials."""

    __tablename__ = "client_credentials"

    client_id = Column(String(255), primary_key=True, index=True)
    client_secret = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ClientCredential(client_id='{self.client_id}', is_active={self.is_active})>"

