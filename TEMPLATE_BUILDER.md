# Template Builder - Dynamic Prompt Construction

The template builder dynamically constructs prompts from any config structure, making it flexible and extensible.

## How It Works

The `PromptTemplateBuilder` class:
1. **Dynamically processes** any config structure
2. **Automatically formats** sections based on their type (string, list, dict)
3. **Handles variables** throughout all sections
4. **Validates** required variables before building

## Config Structure

The builder handles these config types:

### String Sections
```json
{
  "role": "AI assistant",
  "instruction": "Summarize {document}",
  "goal": "Help users understand {topic}"
}
```

**Output:**
```
Role: AI assistant

Instruction: Summarize {document}

Goal: Help users understand {topic}
```

### List Sections (Auto-formatted as bullets)
```json
{
  "output_constraints": [
    "Keep it to {word_count} words",
    "Avoid technical jargon"
  ],
  "style_or_tone": [
    "Use plain language",
    "Be concise"
  ]
}
```

**Output:**
```
Output Constraints:
  - Keep it to {word_count} words
  - Avoid technical jargon

Style Or Tone:
  - Use plain language
  - Be concise
```

### Dictionary Sections (Nested config)
```json
{
  "documentation_requirements": {
    "sections": ["Overview", "Usage"],
    "style": "Clear and concise",
    "format": "Markdown"
  }
}
```

**Output:**
```
Documentation Requirements:
  Sections:
    - Overview
    - Usage
  Style: Clear and concise
  Format: Markdown
```

## Automatic Section Detection

The builder automatically:
- **Detects list sections** and formats them as bullets
- **Detects string sections** and formats them with labels
- **Detects nested dicts** and formats them hierarchically
- **Excludes metadata** sections (variable_schema, metadata, etc.)

## Predefined List Sections

These sections are automatically formatted as bullet lists:
- `output_constraints`
- `style_or_tone`
- `constraints`
- `requirements`
- `guidelines`
- `examples`
- `key_points`

## Custom Formatters

Default formatters for common sections:
- `role` → "Role: {value}"
- `instruction` → "Instruction: {value}"
- `goal` → "Goal: {value}"
- `context` → "Context: {value}"
- `background` → "Background: {value}"

## Variable Handling

### Variables in Config
Variables can be used anywhere in the config:
```json
{
  "instruction": "Summarize {document}",
  "output_constraints": [
    "Keep it to {word_count} words",
    "Focus on {focus_area}"
  ],
  "role": "Writer for {audience_type}"
}
```

### Variable Substitution
```python
from app.services.prompt_template_builder import PromptTemplateBuilder

config = {
    "instruction": "Summarize {document}",
    "output_constraints": ["Keep it to {word_count} words"]
}

variables = {
    "document": "Research paper...",
    "word_count": "100"
}

builder = PromptTemplateBuilder(config, variables)
prompt = builder.build()
```

### Variable Schema (Optional)
```json
{
  "instruction": "Summarize {document}",
  "variable_schema": {
    "document": {
      "required": true,
      "type": "string",
      "description": "Document to summarize"
    },
    "word_count": {
      "required": false,
      "default": "100",
      "description": "Target word count"
    }
  }
}
```

## Usage Examples

### Example 1: Standard Config
```python
config = {
    "role": "AI assistant",
    "instruction": "Write a summary of {document}",
    "output_constraints": [
        "Keep it to {word_count} words",
        "Use plain language"
    ],
    "goal": "Help users understand the content"
}

variables = {
    "document": "Article about AI...",
    "word_count": "150"
}

builder = PromptTemplateBuilder(config, variables)
prompt = builder.build()
```

### Example 2: Custom Sections (Dynamically Handled)
```python
config = {
    "context": "You are analyzing research papers",
    "instruction": "Extract key findings from {document}",
    "requirements": [
        "Focus on methodology",
        "Highlight results"
    ],
    "format": "Structured summary",
    "examples": [
        "Example 1: ...",
        "Example 2: ..."
    ]
}

# Builder automatically handles these new sections!
builder = PromptTemplateBuilder(config, {"document": "..."})
prompt = builder.build()
```

### Example 3: Nested Structure
```python
config = {
    "instruction": "Create documentation",
    "documentation_requirements": {
        "sections": ["Overview", "Installation"],
        "style": "Clear and concise",
        "target_audience": "Developers"
    }
}

builder = PromptTemplateBuilder(config)
prompt = builder.build()
```

## API Integration

The template builder is automatically used by the `PromptTemplate` model:

```python
template = db.query(PromptTemplate).filter_by(id=1).first()
prompt = template.get_full_prompt(
    document="Article content...",
    word_count="100"
)
```

## Benefits

1. **Flexible**: Handles any config structure
2. **Extensible**: Add new sections without code changes
3. **Dynamic**: Automatically formats based on data types
4. **Validated**: Checks required variables before building
5. **Consistent**: Standard formatting across all sections

## Adding New Sections

Just add them to your config - no code changes needed:

```json
{
  "custom_section": "This will be formatted automatically",
  "another_list": ["Item 1", "Item 2"],
  "nested_config": {
    "sub_key": "value"
  }
}
```

The builder will automatically:
- Format strings with labels
- Format lists as bullets
- Format dicts hierarchically

## Variable Extraction

```python
builder = PromptTemplateBuilder(config)
required_vars = builder.get_required_variables()
# Returns: ['document', 'word_count', ...]

schema = builder.get_variable_schema()
# Returns variable schema or auto-generates one
```

## Error Handling

### Missing Variables
```python
# Raises ValueError with clear message
builder = PromptTemplateBuilder(config, {})  # Missing variables
prompt = builder.build()
# ValueError: Missing required variables: document, word_count
```

### Validation
```python
is_valid, missing = builder.validate_variables(variables)
if not is_valid:
    print(f"Missing: {missing}")
```

