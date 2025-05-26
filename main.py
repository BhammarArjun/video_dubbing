# main.py

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Optional
import argparse
import time

# Import our modules
from src.video_downloader import VideoDownloader
from src.asr_processor import ASRProcessor
from src.audio_generator import AudioGenerator
from src.video_combiner import VideoCombiner
from dotenv import load_dotenv
load_dotenv()

class VideoDubbingPipeline:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the video dubbing pipeline"""
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided either as parameter or environment variable")
        
        # Initialize components
        self.video_downloader = VideoDownloader()
        self.asr_processor = ASRProcessor(self.api_key)
        self.audio_generator = AudioGenerator(self.api_key)
        self.video_combiner = VideoCombiner()
        
        # Create main output directory
        self.output_dir = Path("data/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_video(
        self, 
        video_source: str,
        target_language: str,
        video_context: str = "",
        output_filename: str = None,
        session_id: str = None
    ) -> Dict:
        """
        Complete video dubbing pipeline
        
        Args:
            video_source: YouTube URL or local video file path
            target_language: Target language for dubbing (e.g., "Hindi", "Spanish")
            video_context: Additional context about the video content
            output_filename: Custom output filename
            session_id: Unique session identifier
            
        Returns:
            Dictionary with processing results and file paths
        """
        if not session_id:
            session_id = f"dubbing_{int(time.time())}"
        
        print(f"🎬 Starting video dubbing pipeline (Session: {session_id})")
        print(f"📝 Target language: {target_language}")
        
        results = {
            'session_id': session_id,
            'target_language': target_language,
            'steps': {}
        }
        
        try:
            # Step 1: Download/prepare video
            print("\n🔽 Step 1: Preparing video...")
            video_result = self.video_downloader.prepare_video(video_source)
            print(video_result)
            results['steps']['video_preparation'] = video_result
            
            if not video_result['success']:
                return self._error_result(results, "Video preparation failed", video_result['error'])
            
            video_path = video_result['video_path']
            print(f"✅ Video prepared: {video_path}")
            
            # Step 2: Generate transcript using Gemini ASR
            print("\n🎤 Step 2: Generating transcript with speaker analysis...")
            
            transcript_result = self.asr_processor.process_youtube_url_for_transcript(
                    video_source, target_language, video_context
                )
            
            results['steps']['transcript_generation'] = transcript_result
            
            if not transcript_result['success']:
                return self._error_result(results, "Transcript generation failed", transcript_result['error'])
            
            transcript_data = transcript_result['transcript']
            print(f"✅ Transcript generated with {len(transcript_data.get('speaker_profiles', []))} speakers")
            print(f"📄 Total segments: {len(transcript_data.get('dubbing_segments', []))}")
            
            # Step 3: Generate dubbed audio
            print("\n🔊 Step 3: Generating dubbed audio...")
            audio_result = self.audio_generator.generate_audio_from_transcript(
                transcript_data, session_id
            )
            results['steps']['audio_generation'] = audio_result
            
            if not audio_result['success']:
                return self._error_result(results, "Audio generation failed", audio_result['error'])
            
            dubbed_audio_path = audio_result['final_audio_path']
            print(f"✅ Audio generated: {dubbed_audio_path}")
            print(f"🎵 Generated {audio_result['total_segments']} audio segments")
            
            # Step 4: Combine video with dubbed audio
            print("\n🎞️ Step 4: Combining video with dubbed audio...")
            if not output_filename:
                video_name = Path(video_path).stem
                output_filename = f"{video_name}_dubbed_{target_language.lower()}.mp4"
            
            combine_result = self.video_combiner.combine_video_with_audio(
                video_path, dubbed_audio_path, output_filename
            )
            results['steps']['video_combination'] = combine_result
            
            if not combine_result['success']:
                return self._error_result(results, "Video combination failed", combine_result['error'])
            
            final_video_path = combine_result['output_path']
            print(f"✅ Final dubbed video created: {final_video_path}")
            
            # Success summary
            results.update({
                'success': True,
                'final_video_path': final_video_path,
                'transcript_file': transcript_result['transcript_file'],
                'dubbed_audio_path': dubbed_audio_path,
                'voice_assignments': audio_result.get('voice_assignments', {}),
                'processing_summary': {
                    'speakers_detected': len(transcript_data.get('speakers', {})),
                    'segments_processed': len(transcript_data.get('transcript_segments', [])),
                    'final_file_size_mb': round(combine_result['file_size'] / (1024*1024), 2)
                }
            })
            
            print(f"\n🎉 Video dubbing completed successfully!")
            print(f"📁 Output file: {final_video_path}")
            print(f"📊 File size: {results['processing_summary']['final_file_size_mb']} MB")
            
            return results
            
        except Exception as e:
            return self._error_result(results, "Pipeline execution failed", str(e))
    
    def _error_result(self, results: Dict, message: str, error: str) -> Dict:
        """Helper to create error result"""
        results.update({
            'success': False,
            'error_message': message,
            'error_details': error
        })
        print(f"❌ {message}: {error}")
        return results
    
    def preview_transcript(self, video_source: str, target_language: str, video_context: str = "") -> Dict:
        """
        Generate and preview transcript without creating audio/video
        
        Args:
            video_source: YouTube URL or local video file path
            target_language: Target language for transcript
            video_context: Additional context about the video
            
        Returns:
            Dictionary with transcript data
        """
        print(f"📝 Generating transcript preview for {target_language}")
        
        try:
            result = self.asr_processor.process_video_for_transcript(
                    video_source, target_language, video_context
                )
            
            if result['success']:
                transcript = result['transcript']
                print(f"✅ Transcript preview generated:")
                print(f"👥 Speakers: {list(transcript.get('speakers', {}).keys())}")
                print(f"📄 Segments: {len(transcript.get('transcript_segments', []))}")
                
                # Show first few segments
                segments = transcript.get('transcript_segments', [])[:3]
                for i, segment in enumerate(segments):
                    print(f"  {i+1}. [{segment.get('speaker')}] {segment.get('start_time')} - {segment.get('end_time')}")
                    print(f"     \"{segment.get('text', '')[:100]}{'...' if len(segment.get('text', '')) > 100 else ''}\"")
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Transcript preview failed: {e}"
            }
    
    def cleanup_session(self, session_id: str):
        """Clean up temporary files for a session"""
        try:
            session_dir = Path("data/audio_segments") / session_id
            if session_dir.exists():
                import shutil
                shutil.rmtree(session_dir)
                print(f"🧹 Cleaned up session: {session_id}")
        except Exception as e:
            print(f"Warning: Could not cleanup session {session_id}: {e}")

def main():
    starting_time = time.time()
    """Command line interface for the video dubbing pipeline"""
    parser = argparse.ArgumentParser(description="AI Video Dubbing Pipeline using Gemini")
    parser.add_argument("video_source", help="YouTube URL or local video file path")
    parser.add_argument("target_language", help="Target language for dubbing (e.g., Hindi, Spanish, French)")
    parser.add_argument("--context", default="", help="Additional context about the video content")
    parser.add_argument("--output", help="Custom output filename")
    parser.add_argument("--preview-only", action="store_true", help="Only generate transcript preview")
    parser.add_argument("--session-id", help="Custom session identifier")
    parser.add_argument("--api-key", help="Gemini API key (if not set as environment variable)")
    parser.add_argument("--cleanup", help="Cleanup specific session ID")
    
    args = parser.parse_args()
    
    # Handle cleanup command
    if args.cleanup:
        pipeline = VideoDubbingPipeline()
        pipeline.cleanup_session(args.cleanup)
        return
    
    try:
        # Initialize pipeline
        pipeline = VideoDubbingPipeline(api_key=args.api_key)
        
        if args.preview_only:
            print("🔍 Generating transcript preview only...")
            # Generate transcript preview only
            result = pipeline.preview_transcript(
                args.video_source,
                args.target_language,
                args.context
            )
            print(result)
        else:
            # Full pipeline execution
            result = pipeline.process_video(
                video_source=args.video_source,
                target_language=args.target_language,
                video_context=args.context,
                output_filename=args.output,
                session_id=args.session_id
            )
        
        print(f"\n🏁 Total processing time: {round(time.time() - starting_time, 2)} seconds")
        # Print results summary
        if result['success']:
            print(f"\n✨ Success! Check your output files:")
            if 'final_video_path' in result:
                print(f"🎬 Final video: {result['final_video_path']}")
            if 'transcript_file' in result:
                print(f"📄 Transcript: {result['transcript_file']}")
        else:
            print(f"\n❌ Failed: {result.get('error_message', 'Unknown error')}")
            if 'error_details' in result:
                print(f"Details: {result['error_details']}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()