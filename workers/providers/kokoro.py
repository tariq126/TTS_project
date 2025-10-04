
import requests
import base64
from typing import List, Dict
from .base import TTSProvider
from utils.logger import logger

class KokoroProvider(TTSProvider):
    """
    Provider for the Kokoro TTS API.
    """
    def __init__(self, api_base_url: str, **kwargs):
        if not api_base_url:
            raise ValueError("Kokoro API base URL is not configured.")
        
        self.api_base_url = api_base_url
        self.headers = {
            'Content-Type': 'application/json'
        }

    def _make_request(self, payload: dict, output_path: str):
        try:
            response = requests.post(self.api_base_url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            if "audio" not in data:
                raise ValueError("No audio data returned from API")

            # Decode Base64 audio
            audio_b64 = data["audio"].split(",")[1]
            audio_bytes = base64.b64decode(audio_b64)

            # Save to file
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to call Kokoro API: {e}")
            raise ConnectionError(f"Failed to call Kokoro API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while generating audio with Kokoro: {e}")
            raise

    def generate_audio(self, text: str, voice_id: str, output_path: str) -> None:
        """
        Generates audio from text and saves it to a file.
        """
        logger.info(f"Generating audio for text: '{text[:30]}...' with Kokoro voice: {voice_id}")
        
        payload = {
            "text": text,
            "voice_id": voice_id
        }
        self._make_request(payload, output_path)

    def get_voices(self) -> List[Dict[str, str]]:
        """
        Returns a list of available voices. For now, it's a static list.
        """
        return [{"name": "Default", "voice_id": "0"}]
