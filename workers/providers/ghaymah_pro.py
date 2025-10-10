import requests
from typing import List, Dict
from .base import TTSProvider
from utils.logger import logger

class GhaymahProProvider(TTSProvider):
    """
    Provider for the Ghaymah Pro Arabic TTS API.
    """
    def __init__(self, api_key: str, api_base_url: str, DIACRITIZER_URL: str, voices: Dict[str, str], **kwargs):
        if not api_key:
            raise ValueError("Ghaymah Pro API key is not configured.")
        if not api_base_url:
            raise ValueError("Ghaymah Pro API base URL is not configured.")
        
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.diacritizer_url = DIACRITIZER_URL
        self.voices = voices
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, payload: dict, output_path: str):
        try:
            response = requests.post(self.api_base_url, headers=self.headers, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to call Ghaymah Pro API: {e}")
            raise ConnectionError(f"Failed to call Ghaymah Pro API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while generating audio with Ghaymah Pro: {e}")
            raise

    def generate_audio(self, text: str, voice_id: str, output_path: str) -> None:
        """
        Generates audio from text and saves it to a file.
        """
        logger.info(f"Generating audio for text: '{text[:30]}...' with Ghaymah Pro voice: {voice_id}")
        
        payload = {
            "input": text,
            "voice": voice_id,
            "response_format": "mp3",
            "speed": 1.0
        }
        self._make_request(payload, output_path)

    def get_voices(self) -> List[Dict[str, str]]:
        """
        Returns a list of available voices from the configuration.
        """
        return [{"name": name, "voice_id": voice_id} for name, voice_id in self.voices.items()]