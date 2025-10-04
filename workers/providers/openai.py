import requests
from typing import List, Dict
from .base import TTSProvider
from utils.logger import logger

class OpenAIProvider(TTSProvider):
    """
    TTS Provider implementation for OpenAI or any compatible API.
    """
    def __init__(self, api_key: str, voices: Dict[str, str], base_url: str):
        if not api_key:
            raise ValueError("API key for this provider is required but was not found.")
        self.api_key = api_key
        self.base_url = base_url
        self.voices = voices
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _make_request(self, payload: dict, output_path: str):
        try:
            response = requests.post(
                f"{self.base_url}/audio/speech",
                headers=self.headers,
                json=payload,
                stream=True
            )
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to call OpenAI compatible API: {e}")
            raise ConnectionError(f"Failed to call OpenAI compatible API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while generating audio with OpenAI compatible API: {e}")
            raise

    def generate_audio(self, text: str, voice_id: str, output_path: str) -> None:
        """
        Generates audio by calling the external API and streaming the response.
        """
        logger.info(f"Generating audio for text: '{text[:30]}...' with OpenAI compatible voice: {voice_id}")
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice_id,
        }
        self._make_request(payload, output_path)

    def get_voices(self) -> List[Dict[str, str]]:
        """
        Returns the list of voices available for this provider from the config.
        """
        return [{"name": name, "voice_id": voice_id} for name, voice_id in self.voices.items()]