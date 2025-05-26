# src/video_combiner.py

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

class VideoCombiner:
    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self.ffmpeg_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.ffmpeg_available = False
            print("Warning: ffmpeg not found. Video combining may not work.")
    
    def combine_video_with_audio(
        self, 
        video_path: str, 
        audio_path: str, 
        output_filename: str = None,
        replace_audio: bool = True
    ) -> Dict:
        """
        Combine video with generated dubbed audio
        
        Args:
            video_path: Path to original video file
            audio_path: Path to dubbed audio file
            output_filename: Custom output filename (optional)
            replace_audio: If True, replace original audio; if False, mix with original
            
        Returns:
            Dictionary with result information
        """
        if not self.ffmpeg_available:
            return {
                'success': False,
                'error': 'ffmpeg not available for video processing'
            }
        
        try:
            # Generate output filename if not provided
            if not output_filename:
                video_name = Path(video_path).stem
                output_filename = f"{video_name}_dubbed.mp4"
            
            output_path = self.output_dir / output_filename
            
            # Build ffmpeg command
            if replace_audio:
                # Replace original audio completely
                cmd = [
                    'ffmpeg', '-y',  # -y to overwrite output file
                    '-i', video_path,  # Input video
                    '-i', audio_path,  # Input audio
                    '-c:v', 'copy',    # Copy video stream without re-encoding
                    '-c:a', 'aac',     # Encode audio as AAC
                    '-map', '0:v:0',   # Use video from first input
                    '-map', '1:a:0',   # Use audio from second input
                    '-shortest',       # End when shortest stream ends
                    str(output_path)
                ]
            else:
                # Mix original audio with dubbed audio
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-i', audio_path,
                    '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    str(output_path)
                ]
            
            # Execute ffmpeg command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            return {
                'success': True,
                'output_path': str(output_path),
                'output_filename': output_filename,
                'file_size': os.path.getsize(output_path),
                'command_used': ' '.join(cmd)
            }
            
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'error': f'ffmpeg failed: {e.stderr}',
                'command': ' '.join(cmd) if 'cmd' in locals() else 'N/A'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Video combination failed: {e}'
            }
    
    