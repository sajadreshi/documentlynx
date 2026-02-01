"""Example demonstrating dynamic prompt building from config.

Run from project root: python3 -m examples.template_builder_example
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.prompt_template_builder import PromptTemplateBuilder

# Example 1: Basic config with standard sections
config1 = {
    "role": "An AI communicator writing for a general public audience",
    "instruction": "Write a summary of the following {document_type}: {document}",
    "output_constraints": [
        "Keep the summary to approximately {word_count} words",
        "Avoid bullet points or section headers"
    ],
    "style_or_tone": [
        "Use plain, everyday language",
        "Direct and confident"
    ],
    "goal": "Help {target_audience} decide whether this {document_type} is worth reading"
}

variables1 = {
    "document": "This is a research paper about machine learning...",
    "document_type": "research paper",
    "word_count": "100",
    "target_audience": "curious non-experts"
}

builder1 = PromptTemplateBuilder(config1, variables1)
prompt1 = builder1.build()
print("Example 1 - Standard Config:")
print("=" * 80)
print(prompt1)
print("\n")

# Example 2: Custom config with new sections (dynamically handled)
config2 = {
    "context": "You are analyzing scientific publications",
    "instruction": "Extract key findings from {document}",
    "requirements": [
        "Focus on methodology",
        "Highlight statistical significance",
        "Note any limitations"
    ],
    "format": "Structured summary with sections",
    "examples": [
        "Example 1: Methodology section should include...",
        "Example 2: Results should highlight..."
    ],
    "additional_notes": "Pay special attention to {focus_area}"
}

variables2 = {
    "document": "Research paper content...",
    "focus_area": "experimental design"
}

builder2 = PromptTemplateBuilder(config2, variables2)
prompt2 = builder2.build()
print("Example 2 - Custom Config Sections:")
print("=" * 80)
print(prompt2)
print("\n")

# Example 3: Nested config structure
config3 = {
    "role": "Technical writer",
    "instruction": "Create documentation for {feature_name}",
    "documentation_requirements": {
        "sections": [
            "Overview",
            "Installation",
            "Usage examples"
        ],
        "style": "Clear and concise",
        "target_audience": "Developers"
    },
    "output_format": "Markdown"
}

variables3 = {
    "feature_name": "API Authentication"
}

builder3 = PromptTemplateBuilder(config3, variables3)
prompt3 = builder3.build()
print("Example 3 - Nested Config:")
print("=" * 80)
print(prompt3)
print("\n")

# Example 4: Variable extraction
config4 = {
    "instruction": "Analyze {data_source} and provide insights about {metric}",
    "constraints": [
        "Use {analysis_method}",
        "Include {visualization_type} charts"
    ]
}

builder4 = PromptTemplateBuilder(config4)
required_vars = builder4.get_required_variables()
print("Example 4 - Variable Extraction:")
print("=" * 80)
print(f"Required variables: {required_vars}")
print("\n")

# Example 5: Variable schema
config5 = {
    "instruction": "Process {input_data}",
    "variable_schema": {
        "input_data": {
            "required": True,
            "type": "string",
            "description": "Data to process"
        },
        "output_format": {
            "required": False,
            "default": "JSON",
            "description": "Desired output format"
        }
    }
}

builder5 = PromptTemplateBuilder(config5)
schema = builder5.get_variable_schema()
print("Example 5 - Variable Schema:")
print("=" * 80)
import json
print(json.dumps(schema, indent=2))

