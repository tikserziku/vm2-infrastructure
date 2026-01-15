#!/usr/bin/env python3
"""
Real Downloader - Video/Audio downloader using yt-dlp
"""

import subprocess
import os
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_DIR = Path("/home/ubuntu/tiktok-transcriber/audio_files")
AUDIO_DIR.mkdir(exist_ok=True)

def get_yt_dlp_path():
    """Get path to yt-dlp binary"""
    paths = [
        "/usr/local/bin/yt-dlp",
        "/home/ubuntu/.local/bin/yt-dlp",
        "yt-dlp"
    ]
    for path in paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"Found yt-dlp at {path}, version: {result.stdout.strip()}")
                return path
        except:
            continue
    return "yt-dlp"

def download_video(url, output_dir=None):
    """Download video from URL"""
    if output_dir is None:
        output_dir = AUDIO_DIR
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    video_id = str(uuid.uuid4())[:8]
    output_path = output_dir / f"{video_id}.mp4"
    
    yt_dlp = get_yt_dlp_path()
    
    cmd = [
        yt_dlp,
        "-f", "best[ext=mp4]/best",
        "-o", str(output_path),
        "--no-playlist",
        "--no-warnings",
        url
    ]
    
    logger.info(f"Downloading video: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        logger.error(f"Download failed: {result.stderr}")
        raise Exception(f"Download failed: {result.stderr}")
    
    if output_path.exists():
        logger.info(f"Video downloaded: {output_path}")
        return str(output_path)
    
    # Check for different extension
    for ext in ['.webm', '.mkv', '.mp4']:
        alt_path = output_dir / f"{video_id}{ext}"
        if alt_path.exists():
            return str(alt_path)
    
    raise Exception("Downloaded file not found")

def extract_audio(url, output_dir=None):
    """Extract audio from video URL"""
    if output_dir is None:
        output_dir = AUDIO_DIR
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    audio_id = str(uuid.uuid4())[:8]
    output_path = output_dir / f"{audio_id}.mp3"
    
    yt_dlp = get_yt_dlp_path()
    
    cmd = [
        yt_dlp,
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", str(output_dir / f"{audio_id}.%(ext)s"),
        "--no-playlist",
        "--no-warnings",
        url
    ]
    
    logger.info(f"Extracting audio: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        logger.error(f"Audio extraction failed: {result.stderr}")
        raise Exception(f"Audio extraction failed: {result.stderr}")
    
    # Find the output file
    if output_path.exists():
        logger.info(f"Audio extracted: {output_path}")
        return str(output_path), audio_id
    
    # Check other formats
    for ext in ['.mp3', '.m4a', '.opus', '.webm']:
        alt_path = output_dir / f"{audio_id}{ext}"
        if alt_path.exists():
            logger.info(f"Audio extracted: {alt_path}")
            return str(alt_path), audio_id
    
    raise Exception("Extracted audio file not found")

if __name__ == "__main__":
    # Test
    print("Real Downloader module loaded successfully")
    print(f"yt-dlp path: {get_yt_dlp_path()}")

