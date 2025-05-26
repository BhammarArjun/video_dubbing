# src/audio_generator.py

import os
import wave
import json
import time
from pathlib import Path
from google import genai
from google.genai import types
from pydub import AudioSegment
import librosa
import soundfile as sf
import numpy as np
from typing import Dict, List, Tuple
from config.voices import VoiceSelector
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
import base64


class AudioGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not provided")
        
        self.client = genai.Client(api_key=self.api_key)
        self.openai_client = OpenAI()
        self.tts_model = "gemini-2.5-flash-preview-tts"
        self.voice_selector = VoiceSelector()
        
        # Create directories
        self.audio_segments_dir = Path("data/audio_segments")
        self.output_dir = Path("data/output")
        self.audio_segments_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_audio_from_transcript(self, transcript_data: Dict, session_id: str = "default") -> Dict:
        """
        Generate audio segments from transcript data
        
        Args:
            transcript_data: Structured transcript from ASR
            session_id: Unique identifier for this dubbing session
            
        Returns:
            Dictionary with generated audio files and metadata
        """
        try:
            # Create session directory
            session_dir = self.audio_segments_dir / session_id
            session_dir.mkdir(exist_ok=True)
            
            # Get Speker profiles
            speaker_profiles = transcript_data.get('speaker_profiles', [])
            speaker_tts_mapping = {speaker['speaker_id']: speaker['tts_instruction_key'] for speaker in speaker_profiles}

            # Get voice assignments for all speakers
            voice_assignments = self.voice_selector.get_speaker_voices(speaker_profiles)
            
            generated_segments = []
            total_segments = len(transcript_data.get('dubbing_segments', []))
            
            print(f"Generating audio for {total_segments} segments...")
            
            # Process each transcript segment
            for i, segment in enumerate(transcript_data.get('dubbing_segments', [])):
                # keep rate limit of 15 requests per minute
                if i > 0 and i % 20 == 0:
                    print("Rate limit reached, waiting for 60 seconds...")
                    time.sleep(70)

                print(f"Processing segment {i+1}/{total_segments}")
                
                segment_result = self._generate_segment_audio(
                    segment, voice_assignments,speaker_tts_mapping, session_dir, i
                )
                
                if segment_result['success']:
                    generated_segments.append(segment_result)
                else:
                    print(f"Warning: Failed to generate segment {i}: {segment_result.get('error')}")
            
            # Combine all segments into final audio
            final_audio_path = self._combine_audio_segments(generated_segments, session_id)
            
            return {
                'success': True,
                'session_id': session_id,
                'generated_segments': generated_segments,
                'final_audio_path': final_audio_path,
                'voice_assignments': voice_assignments,
                'total_segments': len(generated_segments)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Audio generation failed: {e}"
            }
    
    def _generate_segment_audio(self, segment: Dict, voice_assignments: Dict, speaker_profiles: Dict, session_dir: Path, segment_index: int) -> Dict:
        """Generate audio for a single transcript segment"""
        try:
            speaker = segment.get('speaker_id', 'Speaker 1')
            text = segment.get('translated_text', '')
            start_time = segment.get('start_time', '00:00:00.000')
            end_time = segment.get('end_time', '00:00:00.000')
            target_duration = segment.get('duration_seconds', 0)
            prosody = speaker_profiles.get(speaker, {})
            tts_instruction = "\n\n".join(f"{k}: {v}" for k, v in prosody.items())
            
            if not text.strip():
                return {'success': False, 'error': 'Empty text segment'}
            
            # Get assigned voice for this speaker
            voice_name = voice_assignments.get(speaker, 'onyx')  # Default fallback
            
            # Generate audio using Gemini TTS
            # audio_data = self._call_gemini_tts(text, voice_name)
            audio_data = self._call_openai_tts(text, voice_name, tts_instruction)
            
            if not audio_data:
                return {'success': False, 'error': 'TTS generation failed'}
            
            # Save raw generated audio
            raw_audio_file = session_dir / f"segment_{segment_index:04d}_raw.wav"
            self._save_wave_file(str(raw_audio_file), audio_data)
            
            # Adjust speed to match target duration if needed
            adjusted_audio_file = None
            if target_duration > 0:
                adjusted_audio_file = session_dir / f"segment_{segment_index:04d}_adjusted.wav"
                success = self._adjust_audio_speed(
                    str(raw_audio_file), 
                    str(adjusted_audio_file), 
                    target_duration
                )
                if not success:
                    adjusted_audio_file = raw_audio_file  # Use raw if adjustment fails
            else:
                adjusted_audio_file = raw_audio_file
            
            return {
                'success': True,
                'segment_index': segment_index,
                'speaker': speaker,
                'voice_name': voice_name,
                'text': text,
                'start_time': start_time,
                'end_time': end_time,
                'target_duration': target_duration,
                'raw_audio_file': str(raw_audio_file),
                'final_audio_file': str(adjusted_audio_file),
                'original_segment': segment
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Segment generation failed: {e}",
                'segment_index': segment_index
            }
    
    def _call_gemini_tts(self, text: str, voice_name: str) -> bytes:
        """Call Gemini TTS API to generate audio"""
        try:
            response = self.client.models.generate_content(
                model=self.tts_model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                )
            )
            
            return response.candidates[0].content.parts[0].inline_data.data
            
        except Exception as e:
            print(f"TTS API call failed: {e}")
            return None
        
    def _call_openai_tts(self, text: str, voice_name: str, prosody: str) -> bytes:
        try:
            response = self.openai_client.audio.speech.with_raw_response.create(
                    model="gpt-4o-mini-tts",
                    voice=voice_name,
                    input=text,
                    instructions=prosody,
                    response_format="wav"
            )
            return response.content
        except Exception as e:
            print(f"OpenAI TTS API call failed: {e}")
            return None
    
    def _save_wave_file(self, filename: str, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2):
        """Save PCM data as WAV file"""
        try:
            with wave.open(filename, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(rate)
                wf.writeframes(pcm_data)
        except Exception as e:
            print(f"Error saving wave file: {e}")
    
    def _adjust_audio_speed(self, input_file: str, output_file: str, target_duration: float) -> bool:
        """
        Adjust audio speed to match target duration without pitch distortion.
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            target_duration: Target duration in seconds
            
        Returns:
                True if successful, False otherwise
        """
        try:
            # Load audio, preserving original sample rate (sr=None) and ensuring mono
            # librosa.load defaults to mono. If you need stereo, specify mono=False
            # and handle channels separately or ensure time_stretch supports stereo.
            y, sr = librosa.load(input_file, sr=None) 
            
            current_duration = len(y) / sr

            if current_duration <= 0 or target_duration <= 0:
                print(f"Speed adjustment failed: Invalid duration. Current: {current_duration}s, Target: {target_duration}s")
                return False

            # Calculate speed ratio
            # A ratio > 1 means speed up (shorter duration).
            # A ratio < 1 means slow down (longer duration).
            speed_ratio = current_duration / target_duration

            # --- IMPORTANT CONSIDERATION ---
            # If speed_ratio is very far from 1, artifacts are likely.
            # You might want to add a warning or a threshold here.
            # For example, if abs(speed_ratio - 1) > 0.5 (meaning more than 50% change)
            if not (0.5 <= speed_ratio <= 2.0): # Example threshold: allow 50% slow down to 100% speed up
                print(f"Warning: Extreme speed adjustment ratio detected ({speed_ratio:.2f}). "
                    f"This may result in audible artifacts. (Current: {current_duration:.2f}s, Target: {target_duration:.2f}s)")

            # Apply time stretching using the phase vocoder method
            y_stretched = librosa.effects.time_stretch(y, rate=speed_ratio)

            # Fix the length precisely to match target duration in samples.
            # This will trim or pad the audio to the exact target length.
            target_length_samples = int(target_duration * sr)
            
            # Ensure y_stretched is not empty before fixing length
            if y_stretched.size == 0 and target_length_samples > 0:
                print(f"Speed adjustment failed: time_stretch produced empty audio.")
                return False
            
            y_fixed = librosa.util.fix_length(y_stretched, size=target_length_samples)

            # Save adjusted audio
            sf.write(output_file, y_fixed, sr)
            
            # Optional: Verify output duration for debugging
            output_y, output_sr = librosa.load(output_file, sr=None)
            actual_output_duration = len(output_y) / output_sr
            # print(f"Adjusted audio saved to {output_file}. Original: {current_duration:.2f}s, Target: {target_duration:.2f}s, Actual Output: {actual_output_duration:.2f}s (Ratio: {speed_ratio:.2f})")
            return True

        except FileNotFoundError:
            print(f"Speed adjustment failed: Input file not found at {input_file}")
            return False
        except Exception as e:
            print(f"Speed adjustment failed for {input_file}: {e}")
            return False

    def _combine_audio_segments(self, segments: List[Dict], session_id: str) -> str:
        """
        Combine all audio segments into final dubbed audio track

        Args:
            segments: List of generated segment data
            session_id: Session identifier

        Returns:
            Path to final combined audio file
        """
        try:
            if not segments:
                return ""

            # Sort segments by their index to maintain order
            segments.sort(key=lambda x: x.get('segment_index', 0))

            # Create base silence track (we'll determine total duration)
            combined_audio = AudioSegment.empty()
            last_end_time = 0

            for segment in segments:
                start_time_ms = self._time_to_milliseconds(segment.get('start_time', '00:00:00:000'))

                # Add silence if there's a gap
                if start_time_ms > last_end_time:
                    silence_duration = start_time_ms - last_end_time
                    if silence_duration > 20:  # Skip micro silences to avoid cut sound
                        combined_audio += AudioSegment.silent(duration=silence_duration)

                segment_audio = AudioSegment.from_wav(segment['final_audio_file'])

                # Optional: fade in/out to avoid clicks/pops at joins
                segment_audio = segment_audio.fade_in(10).fade_out(10)

                combined_audio += segment_audio
                last_end_time = start_time_ms + len(segment_audio)

            # Export final combined audio
            final_audio_file = self.output_dir / f"dubbed_audio_{session_id}.wav"
            combined_audio.export(str(final_audio_file), format="wav")

            return str(final_audio_file)

        except Exception as e:
            print(f"Audio combination failed: {e}")
            return ""

    def _time_to_milliseconds(self, time_str: str) -> int:
        """Convert time string (HH:MM:SS:mmm) or (MM:SS:mmm) to milliseconds"""
        try:
            parts = time_str.split(':')

            if len(parts) == 4:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                milliseconds = int(parts[3].ljust(3, '0'))  # pad if needed
            elif len(parts) == 3:
                hours = 0
                minutes = int(parts[0])
                seconds = int(parts[1])
                milliseconds = int(parts[2].ljust(3, '0'))
            else:
                raise ValueError(f"Unexpected time format: {time_str}")

            total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
            return total_ms

        except Exception as e:
            print(f"Time parsing error: {e}")
            return 0

