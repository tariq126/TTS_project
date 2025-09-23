# workers/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict

class TTSProvider(ABC):
    """
    Abstract base class for a Text-to-Speech provider.
    This defines the "contract" that all specific provider implementations must follow.
    """

    @abstractmethod
    def generate_audio(self, text: str, voice_id: str, output_path: str) -> None:
        """
        Generates audio from text and saves it to a file.

        Args:
            text (str): The text to convert to speech.
            voice_id (str): The specific voice to use for the generation.
            output_path (str): The path to save the generated audio file.
        """
        pass

    @abstractmethod
    def get_voices(self) -> List[Dict[str, str]]:
        """
        Retrieves a list of available voices for this provider.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each representing a voice.
            e.g., [{"name": "Rachel", "voice_id": "21m00Tcm4TlvDq8ikWAM"}]
        """
        pass