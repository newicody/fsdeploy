"""
fsdeploy.function.stream.youtube
=================================
Pipeline ffmpeg → YouTube RTMP.

Gère le lancement, l'arrêt, le monitoring du stream.
Utilisable depuis l'initramfs (mode stream) ou le système booté.
"""

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from scheduler.model.task import Task
from scheduler.model.resource import Resource, STREAM, NETWORK
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


RTMP_URL = "rtmp://a.rtmp.youtube.com/live2"


@security.stream.start
class StreamStartTask(Task):
    """Lance un stream YouTube via ffmpeg."""

    def required_resources(self):
        return [STREAM, NETWORK]

    def required_locks(self):
        return [Lock("stream", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        stream_key = self.params.get("stream_key", "")
        resolution = self.params.get("resolution", "1920x1080")
        fps = self.params.get("fps", 30)
        bitrate = self.params.get("bitrate", "4500k")
        audio_bitrate = self.params.get("audio_bitrate", "128k")
        start_delay = self.params.get("start_delay", 0)
        input_source = self.params.get("input", "/dev/fb0")  # framebuffer par défaut

        if not stream_key:
            raise ValueError("stream_key required")

        if start_delay > 0:
            time.sleep(start_delay)

        # Construire la commande ffmpeg
        width, height = resolution.split("x")

        cmd = [
            "ffmpeg",
            "-f", "rawvideo",
            "-pixel_format", "bgra",
            "-video_size", resolution,
            "-framerate", str(fps),
            "-i", input_source,
            # Audio silencieux (YouTube exige un flux audio)
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            # Encodage
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", f"{int(bitrate.replace('k','')) * 2}k",
            "-pix_fmt", "yuv420p",
            "-g", str(fps * 2),
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-ar", "44100",
            # Output
            "-f", "flv",
            f"{RTMP_URL}/{stream_key}",
        ]

        # Lancer en background
        pid_file = Path("/run/fsdeploy-stream.pid")
        log_file = Path("/var/log/fsdeploy/stream.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "a") as log:
            proc = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
            )

        pid_file.write_text(str(proc.pid))

        # Vérifier que le process est vivant après 3s
        time.sleep(3)
        if proc.poll() is not None:
            raise RuntimeError(f"ffmpeg exited with code {proc.returncode}")

        return {
            "pid": proc.pid,
            "stream_key": stream_key[:4] + "****",
            "resolution": resolution,
            "fps": fps,
            "bitrate": bitrate,
            "running": True,
        }


@security.stream.stop
class StreamStopTask(Task):
    """Arrête le stream YouTube."""

    def run(self) -> dict[str, Any]:
        pid_file = Path("/run/fsdeploy-stream.pid")

        if not pid_file.exists():
            return {"running": False, "message": "no stream running"}

        pid = int(pid_file.read_text().strip())

        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            # Attendre la terminaison
            for _ in range(10):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.5)
                except ProcessLookupError:
                    break
            else:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

        pid_file.unlink(missing_ok=True)
        return {"pid": pid, "stopped": True}


@security.stream.status
class StreamStatusTask(Task):
    """Vérifie le statut du stream."""

    def run(self) -> dict[str, Any]:
        pid_file = Path("/run/fsdeploy-stream.pid")

        if not pid_file.exists():
            return {"running": False}

        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            # Lire les dernières lignes de log
            log_file = Path("/var/log/fsdeploy/stream.log")
            last_lines = ""
            if log_file.exists():
                lines = log_file.read_text().splitlines()
                last_lines = "\n".join(lines[-5:])

            return {"running": True, "pid": pid, "last_log": last_lines}
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            return {"running": False, "stale_pid": pid}
