"""Model catalog and provider availability discovery."""

from verdictforge.config import Settings
from verdictforge.schemas import ModelSpec, ProviderName


def build_model_catalog(settings: Settings) -> dict[str, ModelSpec]:
    """Build the public model catalog without exposing provider credentials."""

    nvidia_key = settings.nvidia_api_key or settings.nvidia_openai_api_key
    models = [
        ModelSpec(
            id="llama-3.3-70b",
            display_name="Llama 3.3 70B",
            provider=ProviderName.GROQ,
            model=settings.groq_model,
            description="Fast, capable general-purpose reasoning through Groq.",
            accent="#f97316",
            available=bool(settings.groq_api_key),
        ),
        ModelSpec(
            id="nemotron-nano",
            display_name="Nemotron Nano",
            provider=ProviderName.NVIDIA,
            model=settings.nvidia_model,
            description="NVIDIA-tuned compact reasoning model through NIM.",
            accent="#76b900",
            available=bool(settings.nvidia_api_key),
        ),
        ModelSpec(
            id="gpt-oss-20b",
            display_name="GPT-OSS 20B",
            provider=ProviderName.NVIDIA,
            model=settings.gpt_oss_model,
            description="Open-weight reasoning model served by NVIDIA NIM.",
            accent="#38bdf8",
            available=bool(nvidia_key),
        ),
    ]
    return {model.id: model for model in models}
