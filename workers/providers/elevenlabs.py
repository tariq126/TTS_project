from typing import List, Dict
from elevenlabs.client import ElevenLabs
from .base import TTSProvider

class ElevenLabsProvider(TTSProvider):
    def __init__(self, api_key: str, voices: Dict[str, str]):
        self.client = ElevenLabs(api_key=api_key)
        self.voices = voices

    def generate_audio(self, text: str, voice_id: str, output_path: str) -> None:
        audio = self.client.text_to_speech.convert(voice_id=voice_id, text=text)
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

    def get_voices(self) -> List[Dict[str, str]]:
        return [{"name": name, "voice_id": voice_id} for name, voice_id in self.voices.items()]