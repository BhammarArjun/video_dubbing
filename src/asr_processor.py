import os
import json
from pathlib import Path
from google import genai
from google.genai import types
from config.prompts import get_asr_system_prompt, get_asr_user_prompt
from typing import Dict, Optional
from dotenv import load_dotenv
load_dotenv()

class ASRProcessor:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not provided")
        
        self.client = genai.Client(api_key=self.api_key)
        # self.model = "gemini-2.5-pro-preview-05-06"
        self.model = "gemini-2.5-flash-preview-05-20"
        self.transcript_dir = Path("data/transcripts")
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
    

    def process_youtube_url_for_transcript(
        self,
        youtube_url: str,
        target_language: str,
        video_context: str = ""
    ) -> Dict:
        """
        Process YouTube video directly using URL for transcript generation
        
        Args:
            youtube_url: YouTube video URL
            target_language: Target language for dubbing
            video_context: Additional context about the video
            
        Returns:
            Dictionary containing structured transcript data
        """
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            file_data=types.FileData(
                                file_uri=youtube_url,
                                mime_type="video/*",
                            )
                        ),
                        types.Part.from_text(
                            text=get_asr_user_prompt(target_language, video_context)
                        ),
                    ],
                ),
            ]
            
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=[
                    types.Part.from_text(text=get_asr_system_prompt()),
                ],
                temperature=0.1,
            )
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )
            # print(response)
            transcript_text = response.candidates[0].content.parts[0].text
            transcript_data = json.loads(transcript_text)
            validated_transcript = self._validate_transcript(transcript_data)
            transcript_file = self._save_transcript(validated_transcript, youtube_url, target_language)
            
            return {
                'transcript': validated_transcript,
                'transcript_file': transcript_file,
                'success': True,
                'target_language': target_language
            }
            
        except Exception as e:
            return {
                'error': f"YouTube ASR processing failed: {e}",
                'success': False
            }
    
    def _validate_transcript(self, transcript_data: Dict) -> Dict:
        """Validate and clean up transcript data"""
        try:
            # Ensure required fields exist
            if 'speaker_profiles' not in transcript_data:
                transcript_data['speaker_profiles'] = {}
            
            if 'dubbing_segments' not in transcript_data:
                transcript_data['dubbing_segments'] = []
            
            # Validate speaker data
            for speaker_info in transcript_data['speaker_profiles']:
                if 'gender' not in speaker_info:
                    speaker_info['gender'] = 'male'  # Default fallback
                if 'tts_instruction_key' not in speaker_info:
                    speaker_info['tts_instruction_key'] = {}

            
            # Validate segments
            for segment in transcript_data['dubbing_segments']:
                if 'speaker_id' not in segment:
                    segment['speaker_id'] = 'Speaker 1'
                if 'translated_text' not in segment:
                    segment['translated_text'] = ''
        
            return transcript_data
            
        except Exception as e:
            print(f"Warning: Transcript validation failed: {e}")
            return transcript_data
    
    def _save_transcript(self, transcript_data: Dict, source: str, target_language: str) -> str:
        """Save transcript to JSON file"""
        try:
            # Create filename from source
            if 'youtube.com' in source or 'youtu.be' in source:
                filename = f"youtube_transcript_{target_language}.json"
            else:
                source_name = Path(source).stem
                filename = f"{source_name}_{target_language}.json"
            
            transcript_file = self.transcript_dir / filename
            
            # Add metadata
            transcript_data['metadata'] = {
                'source': source,
                'target_language': target_language,
                'total_segments': len(transcript_data.get('dubbing_segments', [])),
                'total_speakers': len(transcript_data.get('speaker_profiles', []))
            }
            
            with open(transcript_file, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)
            
            return str(transcript_file)
            
        except Exception as e:
            print(f"Warning: Could not save transcript: {e}")
            return ""
    
    def load_transcript(self, transcript_file: str) -> Dict:
        """Load transcript from JSON file"""
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {'error': f"Could not load transcript: {e}", 'success': False}