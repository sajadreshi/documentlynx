# Quick Reference: Prompt Template API

## Authentication Headers (Required for all requests)
```
X-Client-Id: your_client_id
X-Client-Secret: your_client_secret
```

## Base URL
```
http://localhost:8000/documently/api/v1/prompts
```

## Common Operations

### Create Prompt
```bash
POST /prompts
Body: { "name": "...", "config": {...}, "experiment_group": "control" }
```

### List Prompts
```bash
GET /prompts?name=xxx&experiment_group=A&is_active=true
```

### Get Prompt
```bash
GET /prompts/{id}
```

### Render Prompt
```bash
POST /prompts/render
Body: { "name": "...", "user_id": "user123", "variables": {...} }
```

### Update Prompt
```bash
PUT /prompts/{id}
Body: { "description": "...", "config": {...} }
```

### Activate/Deactivate
```bash
POST /prompts/{id}/activate
POST /prompts/{id}/deactivate
```

### Delete Prompt
```bash
DELETE /prompts/{id}
```

## A/B Testing Setup

1. Create control: `experiment_group: "control"`, `traffic_percentage: 0.2`
2. Create variant A: `experiment_group: "A"`, `traffic_percentage: 0.4`
3. Create variant B: `experiment_group: "B"`, `traffic_percentage: 0.4`
4. Render with `user_id` for consistent assignment

## Config Structure
```json
{
  "instruction": "...",
  "output_constraints": ["...", "..."],
  "role": "...",
  "style_or_tone": ["...", "..."],
  "goal": "..."
}
```

