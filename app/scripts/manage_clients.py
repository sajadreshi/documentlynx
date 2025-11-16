"""Script to manage client credentials in the database."""

import sys
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ClientCredential
from app.utils import hash_client_secret


def create_client(client_id: str, client_secret: str) -> None:
    """Create a new client credential."""
    db: Session = SessionLocal()
    try:
        # Check if client already exists
        existing = db.query(ClientCredential).filter(
            ClientCredential.client_id == client_id
        ).first()
        
        if existing:
            print(f"Client with ID '{client_id}' already exists!")
            return
        
        # Hash the secret
        hashed_secret = hash_client_secret(client_secret)
        
        # Create new client
        client = ClientCredential(
            client_id=client_id,
            client_secret=hashed_secret,
            is_active=True
        )
        
        db.add(client)
        db.commit()
        print(f"Client '{client_id}' created successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating client: {str(e)}")
    finally:
        db.close()


def list_clients() -> None:
    """List all client credentials."""
    db: Session = SessionLocal()
    try:
        clients = db.query(ClientCredential).all()
        
        if not clients:
            print("No clients found.")
            return
        
        print("\nClient Credentials:")
        print("-" * 60)
        for client in clients:
            status = "Active" if client.is_active else "Inactive"
            print(f"Client ID: {client.client_id}")
            print(f"Status: {status}")
            print(f"Created: {client.created_at}")
            print("-" * 60)
            
    except Exception as e:
        print(f"Error listing clients: {str(e)}")
    finally:
        db.close()


def deactivate_client(client_id: str) -> None:
    """Deactivate a client credential."""
    db: Session = SessionLocal()
    try:
        client = db.query(ClientCredential).filter(
            ClientCredential.client_id == client_id
        ).first()
        
        if not client:
            print(f"Client with ID '{client_id}' not found!")
            return
        
        client.is_active = False
        db.commit()
        print(f"Client '{client_id}' deactivated successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error deactivating client: {str(e)}")
    finally:
        db.close()


def activate_client(client_id: str) -> None:
    """Activate a client credential."""
    db: Session = SessionLocal()
    try:
        client = db.query(ClientCredential).filter(
            ClientCredential.client_id == client_id
        ).first()
        
        if not client:
            print(f"Client with ID '{client_id}' not found!")
            return
        
        client.is_active = True
        db.commit()
        print(f"Client '{client_id}' activated successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error activating client: {str(e)}")
    finally:
        db.close()


def delete_client(client_id: str) -> None:
    """Delete a client credential."""
    db: Session = SessionLocal()
    try:
        client = db.query(ClientCredential).filter(
            ClientCredential.client_id == client_id
        ).first()
        
        if not client:
            print(f"Client with ID '{client_id}' not found!")
            return
        
        db.delete(client)
        db.commit()
        print(f"Client '{client_id}' deleted successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error deleting client: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m app.scripts.manage_clients create <client_id> <client_secret>")
        print("  python -m app.scripts.manage_clients list")
        print("  python -m app.scripts.manage_clients activate <client_id>")
        print("  python -m app.scripts.manage_clients deactivate <client_id>")
        print("  python -m app.scripts.manage_clients delete <client_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) != 4:
            print("Usage: python -m app.scripts.manage_clients create <client_id> <client_secret>")
            sys.exit(1)
        create_client(sys.argv[2], sys.argv[3])
    
    elif command == "list":
        list_clients()
    
    elif command == "activate":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_clients activate <client_id>")
            sys.exit(1)
        activate_client(sys.argv[2])
    
    elif command == "deactivate":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_clients deactivate <client_id>")
            sys.exit(1)
        deactivate_client(sys.argv[2])
    
    elif command == "delete":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_clients delete <client_id>")
            sys.exit(1)
        delete_client(sys.argv[2])
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

