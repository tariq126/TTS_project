# workers/providers/__init__.py

import config
from .elevenlabs import ElevenLabsProvider
from .openai import OpenAIProvider

PROVIDER_CLASS_MAP = {
    "ElevenLabsProvider": ElevenLabsProvider,
    "OpenAIProvider": OpenAIProvider,
}

# --- Dynamic Factory ---
provider_factory = {}
for name, settings in config.TTS_PROVIDERS.items():
    class_name = settings.get("provider_class")
    
    if not class_name:
        print(f"Warning: Missing 'provider_class' for provider '{name}' in config.py. Skipping.")
        continue

    if class_name in PROVIDER_CLASS_MAP:
        ProviderClass = PROVIDER_CLASS_MAP[class_name]
        
        init_args = settings.copy()
        init_args.pop("provider_class")

        # --- ADD THIS TRY...EXCEPT BLOCK ---
        try:
            # Attempt to create an instance of the provider
            provider_factory[name] = ProviderClass(**init_args)
        except Exception as e:
            # If it fails (e.g., missing API key), print a warning and skip it
            print(f"Warning: Failed to initialize provider '{name}'. Error: {e}")
            continue
        # --- END OF BLOCK ---

    else:
        print(f"Warning: Provider class '{class_name}' not found for provider '{name}'.")

print(f"Successfully initialized providers: {list(provider_factory.keys())}")