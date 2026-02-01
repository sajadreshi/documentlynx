#!/bin/bash

# Example API requests for Prompt Template Management
# 
# Prerequisites:
# 1. Set your CLIENT_ID and CLIENT_SECRET
# 2. Make sure the server is running on localhost:8000
# 3. Update the BASE_URL if your server is running elsewhere

# Configuration
BASE_URL="http://localhost:8000/documently/api/v1"
CLIENT_ID="your_client_id"
CLIENT_SECRET="your_client_secret"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Prompt Template Management API Examples ===${NC}\n"

# ============================================================================
# 1. CREATE PROMPT TEMPLATE
# ============================================================================
echo -e "${GREEN}1. Create a new prompt template${NC}"
curl -X POST "${BASE_URL}/prompts" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "version": "v1",
    "description": "Wk2, L1 - Example5: Adds a clear communication goal to guide emphasis and purpose",
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
        "Avoid hype or promotional language",
        "Avoid deeply technical jargon",
        "No buzzwords like \"transformative\" or \"game-changer\"",
        "Avoid overly polished terms like \"delves into,\" \"showcasing,\" or \"leverages\"",
        "Avoid clichés like \"in the realm of,\" \"ushering in,\" or \"a new era of\"",
        "Don'\''t use em dashes (—) or semicolons",
        "Favor short, clear sentences over long compound ones"
      ],
      "goal": "Help a curious non-expert decide whether this publication is worth reading in full."
    },
    "experiment_group": "control",
    "traffic_percentage": 1.0,
    "created_by": "api_user"
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 2. CREATE VARIANT A FOR A/B TESTING
# ============================================================================
echo -e "${GREEN}2. Create variant A for A/B testing${NC}"
curl -X POST "${BASE_URL}/prompts" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
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
    "traffic_percentage": 0.5,
    "created_by": "api_user"
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 3. CREATE VARIANT B FOR A/B TESTING
# ============================================================================
echo -e "${GREEN}3. Create variant B for A/B testing${NC}"
curl -X POST "${BASE_URL}/prompts" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
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
    "traffic_percentage": 0.5,
    "created_by": "api_user"
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 4. LIST ALL PROMPT TEMPLATES
# ============================================================================
echo -e "${GREEN}4. List all prompt templates${NC}"
curl -X GET "${BASE_URL}/prompts" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  | jq '.'

echo -e "\n"

# ============================================================================
# 5. LIST PROMPTS WITH FILTERS
# ============================================================================
echo -e "${GREEN}5. List prompts with filters (name and experiment_group)${NC}"
curl -X GET "${BASE_URL}/prompts?name=summarization_prompt&experiment_group=A&is_active=true" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  | jq '.'

echo -e "\n"

# ============================================================================
# 6. GET SPECIFIC PROMPT TEMPLATE BY ID
# ============================================================================
echo -e "${GREEN}6. Get specific prompt template by ID (replace 1 with actual ID)${NC}"
curl -X GET "${BASE_URL}/prompts/1" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  | jq '.'

echo -e "\n"

# ============================================================================
# 7. RENDER A PROMPT (WITHOUT USER_ID - CONTROL GROUP)
# ============================================================================
echo -e "${GREEN}7. Render a prompt (control group, no A/B testing)${NC}"
curl -X POST "${BASE_URL}/prompts/render" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "variables": {
      "document": "This is a sample article about artificial intelligence and machine learning..."
    }
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 8. RENDER A PROMPT (WITH USER_ID - A/B TESTING)
# ============================================================================
echo -e "${GREEN}8. Render a prompt with user_id for A/B testing${NC}"
curl -X POST "${BASE_URL}/prompts/render" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt",
    "user_id": "user123",
    "variables": {
      "document": "This is a sample article about quantum computing and its applications..."
    }
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 9. RENDER SAME USER AGAIN (SHOULD GET SAME VARIANT)
# ============================================================================
echo -e "${GREEN}9. Render for same user again (should get same variant)${NC}"
curl -X POST "${BASE_URL}/prompts/render" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt",
    "user_id": "user123",
    "variables": {
      "document": "Another article about blockchain technology..."
    }
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 10. UPDATE PROMPT TEMPLATE
# ============================================================================
echo -e "${GREEN}10. Update a prompt template (replace 1 with actual ID)${NC}"
curl -X PUT "${BASE_URL}/prompts/1" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description - now includes better examples",
    "config": {
      "instruction": "Write a comprehensive summary of an article or publication given to you.",
      "output_constraints": [
        "Keep the summary to a single paragraph of approximately 80 to 100 words.",
        "Avoid bullet points or section headers.",
        "Include key statistics if mentioned"
      ],
      "role": "An AI communicator writing for a general public audience interested in technology and innovation",
      "style_or_tone": [
        "Use plain, everyday language",
        "Direct and confident",
        "Personal and human"
      ],
      "goal": "Help a curious non-expert decide whether this publication is worth reading in full."
    },
    "traffic_percentage": 0.8
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 11. UPDATE ONLY SPECIFIC FIELDS
# ============================================================================
echo -e "${GREEN}11. Update only specific fields (description and traffic)${NC}"
curl -X PUT "${BASE_URL}/prompts/1" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description only",
    "traffic_percentage": 0.9
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 12. DEACTIVATE A PROMPT TEMPLATE
# ============================================================================
echo -e "${GREEN}12. Deactivate a prompt template (replace 1 with actual ID)${NC}"
curl -X POST "${BASE_URL}/prompts/1/deactivate" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  | jq '.'

echo -e "\n"

# ============================================================================
# 13. ACTIVATE A PROMPT TEMPLATE
# ============================================================================
echo -e "${GREEN}13. Activate a prompt template (replace 1 with actual ID)${NC}"
curl -X POST "${BASE_URL}/prompts/1/activate" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  | jq '.'

echo -e "\n"

# ============================================================================
# 14. DELETE A PROMPT TEMPLATE
# ============================================================================
echo -e "${GREEN}14. Delete a prompt template (replace 1 with actual ID)${NC}"
echo -e "${BLUE}Note: This is a destructive operation!${NC}"
# Uncomment to actually delete:
# curl -X DELETE "${BASE_URL}/prompts/1" \
#   -H "X-Client-Id: ${CLIENT_ID}" \
#   -H "X-Client-Secret: ${CLIENT_SECRET}"

echo -e "\n"

# ============================================================================
# 15. CREATE A NEW VERSION OF AN EXISTING PROMPT
# ============================================================================
echo -e "${GREEN}15. Create a new version (v2) of an existing prompt${NC}"
curl -X POST "${BASE_URL}/prompts" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "version": "v2",
    "description": "Version 2 - Improved instructions",
    "config": {
      "instruction": "Write a summary of an article or publication given to you. Focus on the main points and key insights.",
      "output_constraints": [
        "Keep the summary to a single paragraph of approximately 80 to 100 words.",
        "Avoid bullet points or section headers.",
        "Highlight the most important findings"
      ],
      "role": "An AI communicator writing for a general public audience interested in technology and innovation",
      "style_or_tone": [
        "Use plain, everyday language",
        "Direct and confident",
        "Personal and human"
      ],
      "goal": "Help a curious non-expert decide whether this publication is worth reading in full."
    },
    "experiment_group": "control",
    "traffic_percentage": 0.3,
    "created_by": "api_user"
  }' | jq '.'

echo -e "\n"

# ============================================================================
# 16. LIST ALL VERSIONS OF A PROMPT
# ============================================================================
echo -e "${GREEN}16. List all versions of a specific prompt name${NC}"
curl -X GET "${BASE_URL}/prompts?name=summarization_prompt_cfg5" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  | jq '.'

echo -e "\n"

# ============================================================================
# 17. RENDER SPECIFIC VERSION
# ============================================================================
echo -e "${GREEN}17. Render a specific version of a prompt${NC}"
curl -X POST "${BASE_URL}/prompts/render" \
  -H "X-Client-Id: ${CLIENT_ID}" \
  -H "X-Client-Secret: ${CLIENT_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarization_prompt_cfg5",
    "version": "v2",
    "variables": {
      "document": "Sample article content here..."
    }
  }' | jq '.'

echo -e "\n"

echo -e "${BLUE}=== All examples completed! ===${NC}"

