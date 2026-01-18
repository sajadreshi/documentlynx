# Prompt Template Management API Examples

This document provides comprehensive examples for using the Prompt Template Management API.

## Prerequisites

1. Server running on `http://localhost:8000`
2. Valid client credentials (Client ID and Client Secret)
3. `jq` installed for pretty JSON output (optional but recommended)

## Authentication

All endpoints require authentication via headers:
```
X-Client-Id: your_client_id
X-Client-Secret: your_client_secret
```

## Base URL

```
http://localhost:8000/documently/api/v1/prompts
```

---

## 1. Create a Prompt Template

**Endpoint:** `POST /documently/api/v1/prompts`

**Example:**
```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "version": "v1",
    "description": "Wk2, L1 - Example5: Adds a clear communication goal",
    "config": {
      "instruction": "Write a summary of an article or publication given to you.",
      "output_constraints": [
        "Keep the summary to a single paragraph of approximately 80 to 100 words.",
        "Avoid bullet points or section headers."
      ],
      "role": "An AI communicator writing for a general public audience interested in technology and innovation",
      "style_or_tone": [
        "Use plain, everyday language",
        "Direct and confident",
        "Personal and human",
        "Avoid hype or promotional language"
      ],
      "goal": "Help a curious non-expert decide whether this publication is worth reading in full."
    },
    "experiment_group": "control",
    "traffic_percentage": 1.0
  }'
```

**Response:**
```json
{
  "id": 1,
  "name": "summarization_prompt_cfg5",
  "version": "v1",
  "description": "Wk2, L1 - Example5: Adds a clear communication goal",
  "config": { ... },
  "experiment_group": "control",
  "traffic_percentage": 1.0,
  "is_active": true,
  "created_at": "2025-01-16T12:00:00Z",
  "updated_at": null,
  "created_by": "api_user",
  "extra_metadata": null
}
```

---

## 2. Create Variant A for A/B Testing

**Endpoint:** `POST /documently/api/v1/prompts`

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt",
    "version": "v1",
    "description": "Variant A - Concise style",
    "config": {
      "instruction": "Write a brief, concise summary of the article.",
      "output_constraints": [
        "Maximum 100 words",
        "Use bullet points for key points"
      ],
      "role": "A professional technical writer",
      "style_or_tone": [
        "Professional and formal",
        "Clear and structured"
      ],
      "goal": "Provide a quick overview for busy professionals"
    },
    "experiment_group": "A",
    "traffic_percentage": 0.5
  }'
```

---

## 3. Create Variant B for A/B Testing

**Endpoint:** `POST /documently/api/v1/prompts`

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt",
    "version": "v1",
    "description": "Variant B - Narrative style",
    "config": {
      "instruction": "Write an engaging narrative summary of the article.",
      "output_constraints": [
        "Single paragraph, 100-120 words",
        "Tell a story, not just facts"
      ],
      "role": "A creative storyteller",
      "style_or_tone": [
        "Engaging and conversational",
        "Story-driven approach"
      ],
      "goal": "Make the reader want to read the full article"
    },
    "experiment_group": "B",
    "traffic_percentage": 0.5
  }'
```

---

## 4. List All Prompt Templates

**Endpoint:** `GET /documently/api/v1/prompts`

```bash
curl -X GET "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret"
```

**Query Parameters:**
- `name` - Filter by template name
- `version` - Filter by version
- `experiment_group` - Filter by experiment group (A, B, control)
- `is_active` - Filter by active status (true/false)

**Example with filters:**
```bash
curl -X GET "http://localhost:8000/documently/api/v1/prompts?name=summarization_prompt&experiment_group=A&is_active=true" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret"
```

---

## 5. Get Specific Prompt Template

**Endpoint:** `GET /documently/api/v1/prompts/{template_id}`

```bash
curl -X GET "http://localhost:8000/documently/api/v1/prompts/1" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret"
```

---

## 6. Render a Prompt (Control Group)

**Endpoint:** `POST /documently/api/v1/prompts/render`

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts/render" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "variables": {
      "document": "This is a sample article about artificial intelligence..."
    }
  }'
```

**Response:**
```json
{
  "prompt": "Role: An AI communicator...\n\nInstruction: Write a summary...",
  "template_name": "summarization_prompt_cfg5",
  "version": "v1",
  "experiment_group": null
}
```

---

## 7. Render a Prompt with A/B Testing

**Endpoint:** `POST /documently/api/v1/prompts/render`

When you provide a `user_id`, the system will consistently assign the user to either variant A or B based on consistent hashing.

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts/render" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt",
    "user_id": "user123",
    "variables": {
      "document": "This is a sample article about quantum computing..."
    }
  }'
```

**Response:**
```json
{
  "prompt": "Role: A professional technical writer...",
  "template_name": "summarization_prompt",
  "version": "v1",
  "experiment_group": "A"
}
```

**Note:** The same `user_id` will always get the same variant (A or B) for consistent testing.

---

## 8. Render Specific Version

**Endpoint:** `POST /documently/api/v1/prompts/render`

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts/render" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "version": "v2",
    "variables": {
      "document": "Sample article content..."
    }
  }'
```

---

## 9. Update Prompt Template

**Endpoint:** `PUT /documently/api/v1/prompts/{template_id}`

You can update all fields or just specific ones:

```bash
curl -X PUT "http://localhost:8000/documently/api/v1/prompts/1" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "config": {
      "instruction": "Updated instruction...",
      "output_constraints": ["Updated constraint"],
      "role": "Updated role",
      "style_or_tone": ["Updated style"],
      "goal": "Updated goal"
    },
    "traffic_percentage": 0.8
  }'
```

**Partial update (only specific fields):**
```bash
curl -X PUT "http://localhost:8000/documently/api/v1/prompts/1" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Only updating description",
    "traffic_percentage": 0.9
  }'
```

---

## 10. Activate Prompt Template

**Endpoint:** `POST /documently/api/v1/prompts/{template_id}/activate`

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts/1/activate" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret"
```

---

## 11. Deactivate Prompt Template

**Endpoint:** `POST /documently/api/v1/prompts/{template_id}/deactivate`

```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts/1/deactivate" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret"
```

---

## 12. Delete Prompt Template

**Endpoint:** `DELETE /documently/api/v1/prompts/{template_id}`

**Warning:** This is a destructive operation and cannot be undone!

```bash
curl -X DELETE "http://localhost:8000/documently/api/v1/prompts/1" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret"
```

---

## Complete A/B Testing Workflow Example

### Step 1: Create Control Group
```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "article_summary",
    "version": "v1",
    "description": "Control - Original prompt",
    "config": { ... },
    "experiment_group": "control",
    "traffic_percentage": 0.2
  }'
```

### Step 2: Create Variant A (30% traffic)
```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "article_summary",
    "version": "v1",
    "description": "Variant A - Short form",
    "config": { ... },
    "experiment_group": "A",
    "traffic_percentage": 0.3
  }'
```

### Step 3: Create Variant B (50% traffic)
```bash
curl -X POST "http://localhost:8000/documently/api/v1/prompts" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "article_summary",
    "version": "v1",
    "description": "Variant B - Long form",
    "config": { ... },
    "experiment_group": "B",
    "traffic_percentage": 0.5
  }'
```

### Step 4: Test Rendering
```bash
# User 1 - Will consistently get same variant
curl -X POST "http://localhost:8000/documently/api/v1/prompts/render" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "article_summary",
    "user_id": "user001",
    "variables": { "document": "..." }
  }'

# User 2 - May get different variant
curl -X POST "http://localhost:8000/documently/api/v1/prompts/render" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "article_summary",
    "user_id": "user002",
    "variables": { "document": "..." }
  }'
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Prompt template 'name' not found or not active"
}
```

### 401 Unauthorized
```json
{
  "detail": "Invalid client credentials"
}
```

### 404 Not Found
```json
{
  "detail": "Prompt template with ID 999 not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "An unexpected error occurred: ..."
}
```

---

## Tips

1. **Consistent A/B Assignment**: The same `user_id` will always get the same variant
2. **Traffic Allocation**: Ensure traffic percentages add up appropriately for your experiment
3. **Version Control**: Use version strings (v1, v2) to track prompt evolution
4. **Testing**: Always test prompts before activating them in production
5. **Monitoring**: Track which variants perform better for your use case

