"""
fsdeploy.function.stream.youtube
=================================
Pipeline ffmpeg → YouTube RTMP.

Gère le lancement, l'arrêt, le monitoring du stream.
Utilisable depuis l'initramfs (mode stream) ou le système booté.

Composants :
  - StreamStartTask : lance ffmpeg vers YouTube
  - StreamStopTask : arrête le stream
  - StreamStatusTask : vérifie l'état du stream
  - StreamTestTask : test de connectivité RTMP
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
PID_FILE = Path("/run/fsdeploy-stream.pid")
LOG_FILE = Path("/var/log/fsdeploy/stream.log")


def _get_stream_pid() -> Optional[int]:
    """Récupère le PID du processus ffmpeg."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Vérifier que le processus existe
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        return None


def _is_stream_running() -> bool:
    """Vérifie si le stream est actif."""
    return _get_stream_pid() is not None


@security.stream.start
class StreamStartTask(Task):
    """
    Lance un stream YouTube via ffmpeg.
    
    Params:
      - stream_key: clé de stream YouTube (OBLIGATOIRE)
      - resolution: résolution vidéo (défaut: 1920x1080)
      - fps: framerate (défaut: 30)
      - bitrate: bitrate vidéo (défaut: 4500k)
      - audio_bitrate: bitrate audio (défaut: 128k)
      - start_delay: délai avant démarrage (défaut: 0)
      - input: source vidéo (défaut: /dev/fb0)
      - rtmp_url: URL RTMP (défaut: YouTube)
    """

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
        input_source = self.params.get("input", "/dev/fb0")
        rtmp_url = self.params.get("rtmp_url", RTMP_URL)

        if not stream_key:
            raise ValueError("stream_key required")

        # Vérifier si déjà en cours
        if _is_stream_running():
            return {
                "status": "already_running",
                "pid": _get_stream_pid(),
            }

        # Attendre si demandé
        if start_delay > 0:
            time.sleep(start_delay)

        # Parser la résolution
        try:
            width, height = resolution.split("x")
        except ValueError:
            width, height = "1920", "1080"

        # Calculer le bufsize
        bitrate_value = int(bitrate.replace("k", ""))
        bufsize = f"{bitrate_value * 2}k"

        # Construire la commande ffmpeg
        cmd = [
            "ffmpeg",
            # Input vidéo (framebuffer)
            "-f", "rawvideo",
            "-pixel_format", "bgra",
            "-video_size", resolution,
            "-framerate", str(fps),
            "-i", input_source,
            # Input audio (silence)
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            # Encodage vidéo
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", bufsize,
            "-pix_fmt", "yuv420p",
            "-g", str(fps * 2),  # keyframe interval
            # Encodage audio
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-ar", "44100",
            # Output
            "-f", "flv",
            f"{rtmp_url}/{stream_key}",
        ]

        # Préparer les fichiers de log
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Lancer en background
        with open(LOG_FILE, "a") as log:
            log.write(f"\n=== Stream started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            log.write(f"Resolution: {resolution}, FPS: {fps}, Bitrate: {bitrate}\n")
            log.flush()

            proc = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
            )

        # Sauvegarder le PID
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid))

        # Attendre un peu et vérifier que le process tourne
        time.sleep(3)
        if proc.poll() is not None:
            # Le process s'est arrêté
            PID_FILE.unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg exited with code {proc.returncode}")

        return {
            "status": "started",
            "pid": proc.pid,
            "stream_key": stream_key[:4] + "****",  # masquer la clé
            "resolution": resolution,
            "fps": fps,
            "bitrate": bitrate,
            "running": True,
        }


@security.stream.stop
class StreamStopTask(Task):
    """Arrête le stream YouTube."""

    def required_locks(self):
        return [Lock("stream", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        pid = _get_stream_pid()
        force = self.params.get("force", False)

        if pid is None:
            return {
                "status": "not_running",
                "stopped": False,
            }

        # Envoyer SIGTERM (ou SIGKILL si force)
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.killpg(os.getpgid(pid), sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Essayer avec sudo
            self.run_cmd(f"kill -{sig.value} {pid}", sudo=True, check=False)

        # Attendre l'arrêt
        deadline = time.time() + 10
        while time.time() < deadline:
            if not _is_stream_running():
                break
            time.sleep(0.5)

        # Nettoyer le PID file
        PID_FILE.unlink(missing_ok=True)

        # Log
        with open(LOG_FILE, "a") as log:
            log.write(f"\n=== Stream stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

        return {
            "status": "stopped",
            "stopped": True,
            "pid": pid,
        }


@security.stream.status
class StreamStatusTask(Task):
    """Vérifie l'état du stream."""

    def run(self) -> dict[str, Any]:
        pid = _get_stream_pid()
        running = pid is not None

        results = {
            "running": running,
            "pid": pid,
        }

        if running:
            # Récupérer des infos sur le process
            try:
                import psutil
                proc = psutil.Process(pid)
                results["cpu_percent"] = proc.cpu_percent(interval=0.5)
                results["memory_mb"] = proc.memory_info().rss / (1024 * 1024)
                results["uptime_seconds"] = time.time() - proc.create_time()
            except ImportError:
                # psutil non disponible
                pass
            except Exception:
                pass

        # Vérifier les dernières lignes du log
        if LOG_FILE.exists():
            try:
                lines = LOG_FILE.read_text().splitlines()
                results["last_log_lines"] = lines[-10:] if lines else []
            except Exception:
                pass

        return results


@security.stream.test
class StreamTestTask(Task):
    """
    Test de connectivité RTMP.
    
    Envoie quelques secondes de signal de test vers YouTube
    pour vérifier que la connexion fonctionne.
    """

    def required_resources(self):
        return [NETWORK]

    def run(self) -> dict[str, Any]:
        stream_key = self.params.get("stream_key", "")
        duration = self.params.get("duration", 10)
        rtmp_url = self.params.get("rtmp_url", RTMP_URL)

        if not stream_key:
            raise ValueError("stream_key required for test")

        # Générer un signal de test (mire + silence)
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"testsrc=duration={duration}:size=1280x720:rate=30",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={duration}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-b:v", "2000k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "flv",
            f"{rtmp_url}/{stream_key}",
        ]

        start_time = time.time()
        result = self.run_cmd(cmd, timeout=duration + 30, check=False)
        elapsed = time.time() - start_time

        return {
            "success": result.success,
            "duration": elapsed,
            "returncode": result.returncode,
            "error": result.stderr if not result.success else None,
        }


@security.stream.restart
class StreamRestartTask(Task):
    """Redémarre le stream."""

    def required_locks(self):
        return [Lock("stream", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        # Récupérer les paramètres actuels depuis la config ou les params
        stream_params = dict(self.params)

        # Arrêter
        stop_task = StreamStopTask(id="restart_stop", params={})
        stop_result = stop_task.run()

        # Attendre un peu
        time.sleep(2)

        # Redémarrer
        start_task = StreamStartTask(id="restart_start", params=stream_params)
        start_result = start_task.run()

        return {
            "restarted": start_result.get("status") == "started",
            "stop_result": stop_result,
            "start_result": start_result,
        }


# Re-exports
__all__ = [
    "StreamStartTask",
    "StreamStopTask",
    "StreamStatusTask",
    "StreamTestTask",
    "StreamRestartTask",
]
