# src/video_downloader.py

import os
import yt_dlp
from pathlib import Path
from typing import Optional, Dict

class VideoDownloader:
    def __init__(self, download_dir: str = "data/videos"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def download_youtube_video(self, url: str, quality: str = "bestvideo+bestaudio/best") -> Dict[str, str]:
        try:
            # Get video metadata
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
            
            video_title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            ext = 'mp4'  # Since merge_output_format is mp4
            output_filename = f"{video_title}.{ext}"
            output_path = self.download_dir / output_filename

            if not output_path.exists():
                ydl_opts = {
                    'outtmpl': str(output_path),
                    'format': quality,
                    'merge_output_format': ext,
                    'writeinfojson': True,
                    'noplaylist': True,
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            if not output_path.exists():
                raise FileNotFoundError("Downloaded video file not found")

            return {
                'video_path': str(output_path),
                'title': video_title,
                'duration': duration,
                'url': url,
                'success': True
            }

        except Exception as e:
            fallback_path = self.download_dir / f"{video_title}.mp4"
            if fallback_path.exists():
                return {
                    'video_path': str(fallback_path),
                    'title': video_title,
                    'duration': duration,
                    'url': url,
                    'success': True,
                    'warning': 'Used fallback path due to error: ' + str(e)
                }

            return {
                'error': str(e),
                'success': False
            }

    def validate_local_video(self, video_path: str) -> Dict[str, str]:
        """
        Validate and get info about local video file
        
        Args:
            video_path: Path to local video file
            
        Returns:
            Dictionary with video info
        """
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Get basic file info
            file_size = os.path.getsize(video_path)
            file_name = os.path.basename(video_path)
            
            # You can add ffprobe here to get duration, codec info, etc.
            # For now, returning basic info
            
            return {
                'video_path': video_path,
                'title': file_name,
                'file_size': file_size,
                'success': True
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'success': False
            }
    
    def prepare_video(self, input_source: str) -> Dict[str, str]:
        """
        Prepare video for processing (download if URL, validate if local path)
        
        Args:
            input_source: YouTube URL or local file path
            
        Returns:
            Dictionary with video information and path
        """
        # Check if it's a YouTube URL
        if 'youtube.com' in input_source or 'youtu.be' in input_source:
            return self.download_youtube_video(input_source)
        else:
            return self.validate_local_video(input_source)
    
    def cleanup_downloads(self, keep_latest: int = 5):
        """
        Clean up old downloaded videos, keeping only the latest ones
        
        Args:
            keep_latest: Number of recent downloads to keep
        """
        try:
            video_files = []
            for ext in ['*.mp4', '*.mkv', '*.webm', '*.avi']:
                video_files.extend(self.download_dir.glob(ext))
            
            # Sort by modification time (newest first)
            video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old files
            for old_file in video_files[keep_latest:]:
                old_file.unlink()
                # Also remove associated .info.json files
                info_file = old_file.with_suffix('.info.json')
                if info_file.exists():
                    info_file.unlink()
                    
        except Exception as e:
            print(f"Warning: Could not cleanup old downloads: {e}")