"""Script to manage prompt templates in the database."""

import sys
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import PromptTemplate
from app.services.prompt_service import PromptService


def create_prompt(
    name: str,
    config_file: str,
    version: str = "v1",
    description: str = None,
    experiment_group: str = "control",
    traffic_percentage: float = 1.0
) -> None:
    """Create a new prompt template from JSON file."""
    db: Session = SessionLocal()
    try:
        # Load config from file
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        service = PromptService(db)
        template = service.create_template(
            name=name,
            config=config,
            version=version,
            description=description,
            experiment_group=experiment_group,
            traffic_percentage=traffic_percentage,
            created_by="cli"
        )
        
        print(f"Prompt template '{name}' v{version} created successfully!")
        print(f"  ID: {template.id}")
        print(f"  Experiment Group: {template.experiment_group}")
        print(f"  Active: {template.is_active}")
        
    except FileNotFoundError:
        print(f"Error: Config file '{config_file}' not found!")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"Error creating prompt template: {str(e)}")
    finally:
        db.close()


def list_prompts(name: str = None) -> None:
    """List all prompt templates."""
    db: Session = SessionLocal()
    try:
        service = PromptService(db)
        
        if name:
            templates = service.list_templates(name=name)
        else:
            templates = service.list_templates()
        
        if not templates:
            print("No prompt templates found.")
            return
        
        print("\nPrompt Templates:")
        print("-" * 80)
        for template in templates:
            status = "Active" if template.is_active else "Inactive"
            print(f"ID: {template.id}")
            print(f"Name: {template.name}")
            print(f"Version: {template.version}")
            print(f"Description: {template.description or 'N/A'}")
            print(f"Experiment Group: {template.experiment_group}")
            print(f"Traffic: {template.traffic_percentage * 100:.1f}%")
            print(f"Status: {status}")
            print(f"Created: {template.created_at}")
            print("-" * 80)
            
    except Exception as e:
        print(f"Error listing prompts: {str(e)}")
    finally:
        db.close()


def show_prompt(template_id: int) -> None:
    """Show details of a specific prompt template."""
    db: Session = SessionLocal()
    try:
        service = PromptService(db)
        template = service.get_template(template_id)
        
        if not template:
            print(f"Prompt template with ID {template_id} not found!")
            return
        
        print(f"\nPrompt Template Details:")
        print("-" * 80)
        print(f"ID: {template.id}")
        print(f"Name: {template.name}")
        print(f"Version: {template.version}")
        print(f"Description: {template.description or 'N/A'}")
        print(f"Experiment Group: {template.experiment_group}")
        print(f"Traffic: {template.traffic_percentage * 100:.1f}%")
        print(f"Active: {template.is_active}")
        print(f"Created: {template.created_at}")
        print(f"Updated: {template.updated_at or 'N/A'}")
        print(f"Created By: {template.created_by or 'N/A'}")
        print("\nConfiguration:")
        print(json.dumps(template.config, indent=2))
        if template.extra_metadata:
            print("\nMetadata:")
            print(json.dumps(template.extra_metadata, indent=2))
        print("-" * 80)
        
    except Exception as e:
        print(f"Error showing prompt: {str(e)}")
    finally:
        db.close()


def render_prompt(template_id: int, variables_file: str = None) -> None:
    """Render a prompt template with optional variables."""
    db: Session = SessionLocal()
    try:
        service = PromptService(db)
        template = service.get_template(template_id)
        
        if not template:
            print(f"Prompt template with ID {template_id} not found!")
            return
        
        # Load variables if provided
        variables = {}
        if variables_file:
            with open(variables_file, 'r') as f:
                variables = json.load(f)
        
        # Render prompt
        prompt_text = template.get_full_prompt(**variables)
        
        print(f"\nRendered Prompt (Template: {template.name} v{template.version}):")
        print("-" * 80)
        print(prompt_text)
        print("-" * 80)
        
    except FileNotFoundError:
        print(f"Error: Variables file '{variables_file}' not found!")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in variables file: {str(e)}")
    except Exception as e:
        print(f"Error rendering prompt: {str(e)}")
    finally:
        db.close()


def activate_prompt(template_id: int) -> None:
    """Activate a prompt template."""
    db: Session = SessionLocal()
    try:
        service = PromptService(db)
        template = service.activate_template(template_id)
        print(f"Prompt template '{template.name}' v{template.version} activated successfully!")
        
    except ValueError as e:
        print(f"Error: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"Error activating prompt: {str(e)}")
    finally:
        db.close()


def deactivate_prompt(template_id: int) -> None:
    """Deactivate a prompt template."""
    db: Session = SessionLocal()
    try:
        service = PromptService(db)
        template = service.deactivate_template(template_id)
        print(f"Prompt template '{template.name}' v{template.version} deactivated successfully!")
        
    except ValueError as e:
        print(f"Error: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"Error deactivating prompt: {str(e)}")
    finally:
        db.close()


def delete_prompt(template_id: int) -> None:
    """Delete a prompt template."""
    db: Session = SessionLocal()
    try:
        service = PromptService(db)
        deleted = service.delete_template(template_id)
        
        if deleted:
            print(f"Prompt template with ID {template_id} deleted successfully!")
        else:
            print(f"Prompt template with ID {template_id} not found!")
        
    except Exception as e:
        db.rollback()
        print(f"Error deleting prompt: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m app.scripts.manage_prompts create <name> <config_file> [version] [description] [group] [traffic]")
        print("  python -m app.scripts.manage_prompts list [name]")
        print("  python -m app.scripts.manage_prompts show <template_id>")
        print("  python -m app.scripts.manage_prompts render <template_id> [variables_file]")
        print("  python -m app.scripts.manage_prompts activate <template_id>")
        print("  python -m app.scripts.manage_prompts deactivate <template_id>")
        print("  python -m app.scripts.manage_prompts delete <template_id>")
        print("\nExample config file (config.json):")
        print(json.dumps({
            "instruction": "Write a summary of an article or publication given to you.",
            "output_constraints": [
                "Keep the summary to a single paragraph of approximately 80 to 100 words.",
                "Avoid bullet points or section headers."
            ],
            "role": "An AI communicator writing for a general public audience...",
            "style_or_tone": [
                "Use plain, everyday language",
                "Direct and confident"
            ],
            "goal": "Help a curious non-expert decide whether this publication is worth reading."
        }, indent=2))
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) < 4:
            print("Usage: python -m app.scripts.manage_prompts create <name> <config_file> [version] [description] [group] [traffic]")
            sys.exit(1)
        name = sys.argv[2]
        config_file = sys.argv[3]
        version = sys.argv[4] if len(sys.argv) > 4 else "v1"
        description = sys.argv[5] if len(sys.argv) > 5 else None
        group = sys.argv[6] if len(sys.argv) > 6 else "control"
        traffic = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
        create_prompt(name, config_file, version, description, group, traffic)
    
    elif command == "list":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        list_prompts(name)
    
    elif command == "show":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_prompts show <template_id>")
            sys.exit(1)
        show_prompt(int(sys.argv[2]))
    
    elif command == "render":
        if len(sys.argv) < 3:
            print("Usage: python -m app.scripts.manage_prompts render <template_id> [variables_file]")
            sys.exit(1)
        template_id = int(sys.argv[2])
        variables_file = sys.argv[3] if len(sys.argv) > 3 else None
        render_prompt(template_id, variables_file)
    
    elif command == "activate":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_prompts activate <template_id>")
            sys.exit(1)
        activate_prompt(int(sys.argv[2]))
    
    elif command == "deactivate":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_prompts deactivate <template_id>")
            sys.exit(1)
        deactivate_prompt(int(sys.argv[2]))
    
    elif command == "delete":
        if len(sys.argv) != 3:
            print("Usage: python -m app.scripts.manage_prompts delete <template_id>")
            sys.exit(1)
        delete_prompt(int(sys.argv[2]))
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

