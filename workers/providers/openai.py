import os
import requests
from typing import List, Dict
from .base import TTSProvider

class OpenAIProvider(TTSProvider):
    """
    TTS Provider implementation for OpenAI or any compatible API.
    """
    def __init__(self, api_key: str, voices: Dict[str, str], base_url: str):
        if not api_key:
            # This error message is now generic to work for any provider using this class.
            raise ValueError("API key for this provider is required but was not found.")
        self.api_key = api_key
        self.base_url = base_url
        self.voices = voices
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def generate_audio(self, text: str, voice_id: str, output_path: str) -> None:
        """
        Generates audio by calling the external API and streaming the response.
        """
        # The voice_id from our config is the actual voice name the API expects.
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice_id,
        }
        
        # The `stream=True` is important for handling binary data like audio efficiently.
        response = requests.post(
            f"{self.base_url}/audio/speech",
            headers=self.headers,
            json=payload,
            stream=True
        )

        # Check for errors from the API
        response.raise_for_status()

        # Write the streamed audio content to the output file
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def get_voices(self) -> List[Dict[str, str]]:
        """
        Returns the list of voices available for this provider from the config.
        """
        return [{"name": name, "voice_id": voice_id} for name, voice_id in self.voices.items()]