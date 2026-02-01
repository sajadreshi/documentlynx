# Prompt Template Management

This system provides a flexible way to manage prompt templates with A/B testing support, using JSONB storage for flexible configuration.

## Features

- ✅ Flexible prompt configuration (instruction, role, style, constraints, etc.)
- ✅ A/B testing with consistent user assignment
- ✅ Version control for prompts
- ✅ Traffic allocation for experiments
- ✅ RESTful API for management
- ✅ CLI tools for easy management
- ✅ No code changes needed to update prompts

## Database Schema

The `prompt_templates` table stores:
- **name**: Template identifier (e.g., "summarization_prompt_cfg5")
- **version**: Version string (e.g., "v1", "v2")
- **config**: JSONB field containing all prompt sections
- **experiment_group**: "A", "B", or "control"
- **traffic_percentage**: 0.0 to 1.0
- **is_active**: Active status

## Prompt Configuration Structure

```json
{
  "instruction": "Write a summary of an article or publication given to you.",
  "output_constraints": [
    "Keep the summary to a single paragraph of approximately 80 to 100 words.",
    "Avoid bullet points or section headers."
  ],
  "role": "An AI communicator writing for a general public audience...",
  "style_or_tone": [
    "Use plain, everyday language",
    "Direct and confident",
    "Personal and human"
  ],
  "goal": "Help a curious non-expert decide whether this publication is worth reading in full."
}
```

## API Endpoints

All endpoints require authentication via `X-Client-Id` and `X-Client-Secret` headers.

### Create Prompt Template
```bash
POST /documently/api/v1/prompts
```

**Request Body:**
```json
{
  "name": "summarization_prompt_cfg5",
  "version": "v1",
  "description": "Wk2, L1 - Example5: Adds a clear communication goal",
  "config": {
    "instruction": "Write a summary...",
    "output_constraints": ["..."],
    "role": "...",
    "style_or_tone": ["..."],
    "goal": "..."
  },
  "experiment_group": "control",
  "traffic_percentage": 1.0
}
```

### List Prompt Templates
```bash
GET /documently/api/v1/prompts?name=summarization&experiment_group=A&is_active=true
```

### Get Prompt Template
```bash
GET /documently/api/v1/prompts/{template_id}
```

### Update Prompt Template
```bash
PUT /documently/api/v1/prompts/{template_id}
```

### Render Prompt
```bash
POST /documently/api/v1/prompts/render
```

**Request Body:**
```json
{
  "name": "summarization_prompt_cfg5",
  "user_id": "user123",
  "variables": {
    "document": "Article content here..."
  }
}
```

### Activate/Deactivate
```bash
POST /documently/api/v1/prompts/{template_id}/activate
POST /documently/api/v1/prompts/{template_id}/deactivate
```

### Delete Prompt Template
```bash
DELETE /documently/api/v1/prompts/{template_id}
```

## CLI Management

### Create a Prompt Template
```bash
python -m app.scripts.manage_prompts create \
  summarization_prompt_cfg5 \
  examples/prompt_config_example.json \
  v1 \
  "Wk2, L1 - Example5" \
  control \
  1.0
```

### List All Prompts
```bash
python -m app.scripts.manage_prompts list
```

### Show Prompt Details
```bash
python -m app.scripts.manage_prompts show 1
```

### Render a Prompt
```bash
python -m app.scripts.manage_prompts render 1 variables.json
```

### Activate/Deactivate
```bash
python -m app.scripts.manage_prompts activate 1
python -m app.scripts.manage_prompts deactivate 1
```

### Delete Prompt
```bash
python -m app.scripts.manage_prompts delete 1
```

## A/B Testing

### Setting Up A/B Test

1. Create variant A:
```bash
python -m app.scripts.manage_prompts create \
  summarization_prompt \
  config_variant_a.json \
  v1 \
  "Variant A" \
  A \
  0.5
```

2. Create variant B:
```bash
python -m app.scripts.manage_prompts create \
  summarization_prompt \
  config_variant_b.json \
  v1 \
  "Variant B" \
  B \
  0.5
```

3. Use the API to render prompts - users will be consistently assigned to A or B based on their user_id hash.

### Consistent Assignment

Users are assigned to experiment groups using consistent hashing:
- Same `name` + `user_id` = Same group assignment
- 50/50 split between A and B
- Stable across requests

## Example Usage in Code

```python
from app.database import get_db
from app.services.prompt_service import PromptService

# Get database session
db = next(get_db())
service = PromptService(db)

# Render a prompt with A/B testing
prompt_text = service.get_prompt(
    name="summarization_prompt_cfg5",
    user_id="user123",  # For consistent A/B assignment
    document="Article content here...",
    requirements="Summarize in 100 words"
)

print(prompt_text)
```

## Best Practices

1. **Version Control**: Use version strings (v1, v2, etc.) for tracking changes
2. **Descriptions**: Always add descriptions for clarity
3. **Traffic Allocation**: Start with small percentages for new variants
4. **Testing**: Test prompts before activating
5. **Monitoring**: Track performance metrics for A/B tests
6. **Rollback**: Keep previous versions active for quick rollback

## Database Migration

The `prompt_templates` table will be automatically created when you start the application. The table structure includes:

- Indexes on `name`, `version`, `experiment_group`, and `is_active` for fast queries
- JSONB column for flexible prompt configuration
- Timestamps for audit trail

