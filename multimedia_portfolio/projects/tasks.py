from celery import shared_task
import subprocess
import shlex
import logging

logger = logging.getLogger('security')


@shared_task
def scan_file_with_clamav(file_path: str) -> dict:
    """
    Scan a file path with ClamAV. Returns a dict with { 'ok': bool, 'output': str }.
    Requires clamd or clamscan to be installed and available on PATH.
    """
    try:
        cmd = f"clamscan --no-summary {shlex.quote(file_path)}"
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        output = proc.stdout + proc.stderr
        infected = 'FOUND' in output and 'OK' not in output
        if infected:
            logger.warning(f"ClamAV detected malware in {file_path}: {output.strip()[:500]}")
        return { 'ok': not infected, 'output': output }
    except Exception as e:
        logger.error(f"ClamAV scan error for {file_path}: {e}")
        return { 'ok': False, 'output': str(e) }


@shared_task
def transcode_video_ffmpeg(input_path: str, output_path: str) -> dict:
    """
    Transcode video using ffmpeg to H.264/AAC MP4 profile.
    Requires ffmpeg installed on PATH.
    """
    try:
        cmd = (
            f"ffmpeg -y -i {shlex.quote(input_path)} -c:v libx264 -preset veryfast -crf 23 "
            f"-c:a aac -b:a 128k -movflags +faststart {shlex.quote(output_path)}"
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        ok = proc.returncode == 0
        if not ok:
            logger.error(f"ffmpeg transcode failed: {proc.stderr[:500]}")
        return { 'ok': ok, 'stderr': proc.stderr, 'stdout': proc.stdout }
    except Exception as e:
        logger.error(f"ffmpeg error: {e}")
        return { 'ok': False, 'error': str(e) }


@shared_task
def transcode_audio_ffmpeg(input_path: str, output_path: str) -> dict:
    """
    Transcode audio using ffmpeg to MP3.
    Requires ffmpeg installed on PATH.
    """
    try:
        cmd = f"ffmpeg -y -i {shlex.quote(input_path)} -codec:a libmp3lame -qscale:a 2 {shlex.quote(output_path)}"
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        ok = proc.returncode == 0
        if not ok:
            logger.error(f"ffmpeg audio transcode failed: {proc.stderr[:500]}")
        return { 'ok': ok, 'stderr': proc.stderr, 'stdout': proc.stdout }
    except Exception as e:
        logger.error(f"ffmpeg error: {e}")
        return { 'ok': False, 'error': str(e) }
