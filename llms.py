import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from dotenv import load_dotenv

load_dotenv()


available_models = [
    "gpt-4o-mini",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "lm-studio",
]


def get_llm(model: str):
    if model not in available_models:
        raise ValueError(f"Invalid model. Available models: {available_models.keys()}")

    if model == "gpt-4o-mini":
        return ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    elif model in ["gemini-1.5-flash", "gemini-1.5-pro"]:
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0.0,
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
    elif model == "lm-studio":
        return ChatOpenAI(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
            model="openai/gpt-oss-20b",
            temperature=0.7,
        )
    elif model in [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "qwen/qwen3-32b",
        "openai/gpt-oss-20b",
    ]:
        return ChatGroq(
            model_name=model,
            temperature=0.0,
            api_key=os.getenv("GROQ_API_KEY"),
        )