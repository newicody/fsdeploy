"""
fsdeploy.core.integrity
========================
Contrôle d'intégrité CRC/hash sur les images et snapshots.

Algorithmes disponibles :
    crc32   — rapide, non cryptographique, suffisant pour corruption disque
    sha256  — cryptographique, lent sur gros fichiers, pour signature
    blake2b — cryptographique rapide (recommandé pour les images > 100 MB)

Un fichier .meta accompagne chaque image/snapshot et contient :
    checksum_algo   = blake2b
    checksum        = <hex>
    checksum_size   = 1234567890   (taille au moment du calcul)
    checksum_date   = 2025-03-14T12:00:00Z

Usage :
    # Calculer et sauvegarder
    ic = IntegrityChecker()
    ic.sign(Path("/boot/images/kernels/vmlinuz-6.6.47"))

    # Vérifier
    ok, msg = ic.verify(Path("/boot/images/kernels/vmlinuz-6.6.47"))

    # Vérifier un répertoire complet
    results = ic.verify_dir(Path("/boot/images"))
    for r in results:
        print(r.icon, r.path, r.message)
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator


# =============================================================================
# ALGORITHMES
# =============================================================================

ALGO_BLAKE2B = "blake2b"
ALGO_SHA256  = "sha256"
ALGO_CRC32   = "crc32"

# Recommandation par taille de fichier
def _recommend_algo(size_bytes: int) -> str:
    if size_bytes > 50 * 1024 * 1024:   # > 50 MB → blake2b (rapide + sûr)
        return ALGO_BLAKE2B
    if size_bytes > 1024 * 1024:         # > 1 MB → sha256
        return ALGO_SHA256
    return ALGO_CRC32                    # petits fichiers → crc32 suffisant


def _compute(path: Path, algo: str, progress_cb: Callable | None = None) -> str:
    """Calcule le checksum d'un fichier. Retourne la valeur hex."""
    CHUNK = 4 * 1024 * 1024  # 4 MB

    if algo == ALGO_CRC32:
        crc = 0
        with path.open("rb") as f:
            while chunk := f.read(CHUNK):
                crc = zlib.crc32(chunk, crc)
                if progress_cb:
                    progress_cb(len(chunk))
        return format(crc & 0xFFFFFFFF, "08x")

    if algo == ALGO_BLAKE2B:
        h = hashlib.blake2b()
    elif algo == ALGO_SHA256:
        h = hashlib.sha256()
    else:
        raise ValueError(f"Algorithme inconnu : {algo}")

    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
            if progress_cb:
                progress_cb(len(chunk))
    return h.hexdigest()


# =============================================================================
# RÉSULTAT DE VÉRIFICATION
# =============================================================================

@dataclass
class CheckResult:
    path:     Path
    ok:       bool
    message:  str
    algo:     str  = ""
    expected: str  = ""
    got:      str  = ""

    @property
    def icon(self) -> str:
        return "✅" if self.ok else "❌"

    def to_dict(self) -> dict:
        return {
            "path":     str(self.path),
            "ok":       self.ok,
            "message":  self.message,
            "algo":     self.algo,
            "expected": self.expected,
            "got":      self.got,
        }


# =============================================================================
# CHECKER PRINCIPAL
# =============================================================================

class IntegrityChecker:
    """
    Calcule, sauvegarde et vérifie les checksums des images et snapshots.

    Le checksum est stocké dans le fichier .meta associé à chaque image.
    Le .meta est un fichier INI simple (pas configobj — pour rester léger
    dans l'initramfs).

    Convention de nommage des .meta :
        vmlinuz-6.6.47           → vmlinuz-6.6.47.meta
        initramfs-zbm-20250314.img → initramfs-zbm-20250314.img.meta
        snap-20250314-143022/     → snap-20250314-143022/snap.meta
    """

    def __init__(
        self,
        default_algo: str = ALGO_BLAKE2B,
        *,
        bypass: bool = False,
    ) -> None:
        self.default_algo = default_algo
        self.bypass = bypass

    # ── Signature ────────────────────────────────────────────────────────────

    def sign(
        self,
        path: Path,
        *,
        algo: str | None = None,
        progress_cb: Callable | None = None,
        extra_meta: dict[str, str] | None = None,
    ) -> str:
        """
        Calcule le checksum de path et le sauvegarde dans le .meta associé.
        Retourne le checksum calculé.
        """
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable : {path}")

        size  = path.stat().st_size
        _algo = algo or _recommend_algo(size)
        value = _compute(path, _algo, progress_cb)
        now   = datetime.now(timezone.utc).isoformat(timespec="seconds")

        meta = self._read_meta(path)
        meta.update({
            "checksum_algo": _algo,
            "checksum":      value,
            "checksum_size": str(size),
            "checksum_date": now,
        })
        if extra_meta:
            meta.update(extra_meta)

        self._write_meta(path, meta)
        return value

    def sign_dir(
        self,
        directory: Path,
        *,
        patterns: list[str] = None,
        algo: str | None = None,
        progress_cb: Callable | None = None,
    ) -> list[tuple[Path, str]]:
        """
        Signe tous les fichiers d'un répertoire correspondant aux patterns.
        Retourne la liste (path, checksum).
        """
        _patterns = patterns or ["*.sfs", "*.img", "*.zst", "vmlinuz*",
                                  "bzImage*", "kernel-*", "initramfs-*",
                                  "modules-*", "rootfs*", "python-*"]
        results = []
        for pat in _patterns:
            for f in sorted(directory.rglob(pat)):
                if f.suffix == ".meta" or not f.is_file():
                    continue
                checksum = self.sign(f, algo=algo, progress_cb=progress_cb)
                results.append((f, checksum))
        return results

    # ── Vérification ─────────────────────────────────────────────────────────

    def verify(self, path: Path, *, progress_cb: Callable | None = None) -> CheckResult:
        """
        Vérifie l'intégrité d'un fichier contre son .meta.
        """
        if self.bypass:
            return CheckResult(path=path, ok=True, message="bypass actif")

        if not path.exists():
            return CheckResult(path=path, ok=False, message="Fichier introuvable")

        meta = self._read_meta(path)

        # Pas de checksum enregistré
        if "checksum" not in meta:
            return CheckResult(
                path=path, ok=False,
                message="Pas de checksum dans le .meta — fichier non signé",
            )

        expected = meta["checksum"]
        algo     = meta.get("checksum_algo", ALGO_BLAKE2B)

        # Vérification de taille rapide
        stored_size = int(meta.get("checksum_size", 0))
        actual_size = path.stat().st_size
        if stored_size and actual_size != stored_size:
            return CheckResult(
                path=path, ok=False, algo=algo,
                message=(
                    f"Taille modifiée : attendu {stored_size} octets, "
                    f"trouvé {actual_size} octets"
                ),
            )

        # Calcul du checksum réel
        got = _compute(path, algo, progress_cb)

        ok = got == expected
        return CheckResult(
            path     = path,
            ok       = ok,
            algo     = algo,
            expected = expected,
            got      = got,
            message  = "OK" if ok else f"Checksum invalide ({algo})",
        )

    def verify_dir(
        self,
        directory: Path,
        *,
        patterns: list[str] = None,
        progress_cb: Callable | None = None,
    ) -> list[CheckResult]:
        """
        Vérifie tous les fichiers signés dans un répertoire.
        Retourne la liste des CheckResult.
        """
        _patterns = patterns or ["*.sfs", "*.img", "*.zst", "vmlinuz*",
                                  "bzImage*", "kernel-*", "initramfs-*",
                                  "modules-*", "rootfs*", "python-*"]
        results = []
        for pat in _patterns:
            for f in sorted(directory.rglob(pat)):
                if f.suffix == ".meta" or not f.is_file():
                    continue
                meta = self._read_meta(f)
                if "checksum" not in meta:
                    continue  # fichier non signé → ignorer silencieusement
                results.append(self.verify(f, progress_cb=progress_cb))
        return results

    def verify_snapshot_dir(self, snap_dir: Path) -> list[CheckResult]:
        """
        Vérifie l'intégrité d'un répertoire de snapshot complet.
        Vérifie tous les .zst + le snap.meta lui-même.
        """
        results = self.verify_dir(snap_dir, patterns=["*.zst"])
        # Vérifier aussi le snap.meta (checksum des checksums)
        meta_file = snap_dir / "snap.meta"
        if meta_file.exists():
            meta = self._read_meta_file(meta_file)
            if "manifest_checksum" in meta:
                manifest = "\n".join(
                    f"{r.path.name}:{r.expected}" for r in results
                ).encode()
                got = hashlib.blake2b(manifest).hexdigest()
                expected = meta["manifest_checksum"]
                ok = got == expected
                results.append(CheckResult(
                    path     = meta_file,
                    ok       = ok,
                    algo     = ALGO_BLAKE2B,
                    expected = expected,
                    got      = got,
                    message  = "Manifeste OK" if ok else "Manifeste corrompu",
                ))
        return results

    def sign_snapshot_manifest(self, snap_dir: Path, file_checksums: list[tuple[Path, str]]) -> None:
        """
        Signe le manifeste d'un snapshot : checksum de tous les checksums.
        Empêche la manipulation d'un .meta individuel sans invalider l'ensemble.
        """
        manifest = "\n".join(
            f"{path.name}:{checksum}" for path, checksum in sorted(file_checksums)
        ).encode()
        manifest_checksum = hashlib.blake2b(manifest).hexdigest()

        meta_file = snap_dir / "snap.meta"
        meta = self._read_meta_file(meta_file) if meta_file.exists() else {}
        meta["manifest_checksum"] = manifest_checksum
        meta["manifest_date"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._write_meta_file(meta_file, meta)

    # ── Lecture / écriture .meta ──────────────────────────────────────────────

    @staticmethod
    def meta_path(path: Path) -> Path:
        """Retourne le chemin du .meta associé à un fichier ou répertoire."""
        if path.is_dir():
            return path / "snap.meta"
        return path.with_suffix(path.suffix + ".meta")

    def _read_meta(self, path: Path) -> dict[str, str]:
        return self._read_meta_file(self.meta_path(path))

    def _write_meta(self, path: Path, data: dict[str, str]) -> None:
        self._write_meta_file(self.meta_path(path), data)

    @staticmethod
    def _read_meta_file(meta_path: Path) -> dict[str, str]:
        if not meta_path.exists():
            return {}
        result: dict[str, str] = {}
        try:
            for line in meta_path.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip()
        except OSError:
            pass
        return result

    @staticmethod
    def _write_meta_file(meta_path: Path, data: dict[str, str]) -> None:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k} = {v}" for k, v in sorted(data.items())]
        meta_path.write_text("\n".join(lines) + "\n")

    # ── Résumé ────────────────────────────────────────────────────────────────

    @staticmethod
    def summary(results: list[CheckResult]) -> dict:
        total = len(results)
        ok    = sum(1 for r in results if r.ok)
        return {
            "total":   total,
            "ok":      ok,
            "failed":  total - ok,
            "healthy": total > 0 and ok == total,
            "failures": [r.to_dict() for r in results if not r.ok],
        }
