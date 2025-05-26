import random
from typing import Dict, List

SPEAKER_STYLES = {
    "alloy": {"gender": "female"},
    "ash": {"gender": "male"},        # best
    "ballad": {"gender": "male"},
    "coral": {"gender": "female"},    # best
    "echo": {"gender": "male"},
    "fable": {"gender": "female"},
    "onyx": {"gender": "male"},       # best
    "nova": {"gender": "female"},     # best
    "sage": {"gender": "female"},
    "shimmer": {"gender": "female"},
    "verse": {"gender": "male"}
}


class VoiceSelector:
    def __init__(self):
        self.speaker_voice_mapping = {}
    
    def get_all_voices(self) -> List[str]:
        """Get all available voice names"""
        return list(SPEAKER_STYLES.keys())
    
    def get_voices_by_gender(self, gender: str, restricted : set = None) -> List[str]:
        """Get all voice names for a specific gender"""
        return [name for name, info in SPEAKER_STYLES.items() 
                if info["gender"].lower() == gender.lower() and name not in restricted]
    
    def assign_voice_to_speaker(self, speaker_id: str, gender: str, restricted : set = None) -> str:
        """Assign a consistent voice to a speaker based on gender and style"""
        
        if speaker_id in self.speaker_voice_mapping:
            return self.speaker_voice_mapping[speaker_id]
        
        available_voices = self.get_voices_by_gender(gender, restricted)
        print(f"Available voices - {available_voices})")

        if not available_voices:
            available_voices = self.get_all_voices()
        
        # Randomly select from available voices
        selected_voice = random.choice(available_voices)
        self.speaker_voice_mapping[speaker_id] = selected_voice
            
    
    def get_speaker_voices(self, speakers_info: List) -> Dict[str, str]:
        """Get voice assignments for all speakers"""
        
        for speaker in speakers_info:
            restricted = set(self.speaker_voice_mapping.values())
            speaker_id = speaker.get("speaker_id").strip()
            gender = speaker.get("gender").lower()

            self.assign_voice_to_speaker(speaker_id, gender, restricted)


        return self.speaker_voice_mapping
