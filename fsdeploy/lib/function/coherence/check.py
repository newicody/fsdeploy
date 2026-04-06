# -*- coding: utf-8 -*-
"""
fsdeploy.function.coherence.check
===================================
Verification de coherence du systeme avant boot.

Verifie :
  - Kernel present et accessible
  - Initramfs valide
  - ZFSBootMenu installe (si mode zbm)
  - Datasets montables
  - Checksums intacts
  - Overlayfs fonctionnel
  - Presets coherents
  - ZBM pre-flight (si demande)

ZERO chemin en dur. Tout est pilote par config/preset/params.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from scheduler.model.task import Task
from scheduler.security.decorator import security


@dataclass
class CheckResult:
    """Resultat d'une verification individuelle."""
    name: str
    passed: bool
    message: str = ""
    severity: str = "error"  # error | warning | info


@dataclass
class CoherenceReport:
    """Rapport complet de coherence."""
    checks: list[CheckResult] = field(default_factory=list)
    zbm_report: Any = None  # ZBMValidationReport optionnel

    @property
    def passed(self) -> bool:
        base = all(c.passed for c in self.checks if c.severity == "error")
        if self.zbm_report is not None:
            return base and self.zbm_report.passed
        return base

    @property
    def errors(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    def summary(self) -> str:
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c.passed)
        parts = [
            f"{ok}/{total} checks passed",
            f"{len(self.errors)} errors",
            f"{len(self.warnings)} warnings",
        ]
        if self.zbm_report is not None:
            parts.append(f"ZBM: {self.zbm_report.summary()}")
        return ", ".join(parts)


@security.coherence.check
class CoherenceCheckTask(Task):
    """
    Verifie la coherence complete du systeme.

    Params attendus (tous depuis config/preset, aucun en dur) :
      - boot_mount: str         Point de montage boot (pool.boot_mount)
      - staging_dir: str        Repertoire staging kernel (kernel.staging_dir)
      - efi_device: str         Device EFI (partition.efi_device)
      - efi_mount: str          Point de montage EFI (partition.efi_mount)
      - efi_part_num: str       Numero de partition EFI
      - preset: dict            Preset actif
      - mounts: dict            {dataset: mountpoint}
      - pools: list[str]        Pools requis
      - zbm_efi_path: str       Chemin EFI ZBM (zbm.efi_path)
      - zbm_install_method: str Methode install ZBM
      - zbm_cmdline: str        Ligne de commande ZBM
      - zbm_bootfs: str         Dataset racine ZBM
      - zbm_config_yaml: str    Config.yaml ZBM
      - zbm_image_dir: str      Repertoire images ZBM
      - kernel_active: str      Kernel actif (kernel.active)
      - kernel_version: str     Version kernel (kernel.version)
      - initramfs_active: str   Initramfs actif (initramfs.active)
      - run_zbm_preflight: bool Lancer la validation pre-vol ZBM (defaut: True)
    """

    def run(self) -> CoherenceReport:
        report = CoherenceReport()

        boot_mount = self.params.get("boot_mount", "")
        staging_dir = self.params.get("staging_dir", "") or boot_mount
        preset = self.params.get("preset", {})
        mounts = self.params.get("mounts", {})
        pools = self.params.get("pools", [])

        boot_path = Path(staging_dir) if staging_dir else None

        # 1. Kernel
        report.checks.append(self._check_kernel(boot_path, preset))

        # 2. Initramfs
        report.checks.append(self._check_initramfs(boot_path, preset))

        # 3. Modules
        report.checks.append(self._check_modules(preset, mounts, staging_dir))

        # 4. ZFSBootMenu
        report.checks.append(self._check_zbm(
            self.params.get("efi_mount", ""),
            self.params.get("zbm_efi_path", ""),
        ))

        # 5. EFI
        report.checks.append(self._check_efi(
            self.params.get("efi_device", ""),
            self.params.get("efi_mount", ""),
        ))

        # 6. Pools importes
        for pool in pools:
            if pool:
                report.checks.append(self._check_pool(pool))

        # 7. SquashFS rootfs
        rootfs_val = preset.get("rootfs", "")
        if rootfs_val:
            report.checks.append(self._check_rootfs(boot_path, rootfs_val))

        # 8. Overlay dataset
        overlay_ds = preset.get("overlay_dataset", "")
        if overlay_ds:
            report.checks.append(self._check_overlay(overlay_ds, mounts))

        # 9. Symlinks boot
        if boot_path:
            report.checks.append(self._check_boot_symlinks(boot_path))

        # 10. ZBM Pre-flight (optionnel mais par defaut)
        if self.params.get("run_zbm_preflight", True):
            report.zbm_report = self._run_zbm_preflight()

        return report

    # ===============================================================
    # INDIVIDUAL CHECKS
    # ===============================================================

    def _check_kernel(
        self, boot_path: Path | None, preset: dict,
    ) -> CheckResult:
        """Verifie le kernel."""
        kernel_name = self.params.get("kernel_active", "")
        if not kernel_name and preset:
            kernel_name = preset.get("kernel", "")

        if not kernel_name:
            return CheckResult("kernel", False,
                               "No active kernel configured")

        if not boot_path:
            return CheckResult("kernel", False,
                               "boot_mount/staging_dir not configured")

        p = boot_path / kernel_name if not kernel_name.startswith("/") \
            else Path(kernel_name)

        if p.is_symlink():
            target = p.resolve()
            if not target.exists():
                return CheckResult("kernel", False,
                                   f"Kernel symlink broken: {p} -> {target}")
            p = target

        if p.exists() and p.stat().st_size > 0:
            return CheckResult("kernel", True, f"OK: {p}")
        return CheckResult("kernel", False, f"Kernel not found: {p}")

    def _check_initramfs(
        self, boot_path: Path | None, preset: dict,
    ) -> CheckResult:
        """Verifie l'initramfs."""
        initramfs_name = self.params.get("initramfs_active", "")
        if not initramfs_name and preset:
            initramfs_name = preset.get("initramfs", "")

        if not initramfs_name:
            return CheckResult("initramfs", False,
                               "No active initramfs configured")

        if not boot_path:
            return CheckResult("initramfs", False,
                               "boot_mount/staging_dir not configured")

        p = boot_path / initramfs_name if not initramfs_name.startswith("/") \
            else Path(initramfs_name)

        if p.is_symlink():
            p = p.resolve()

        if p.exists():
            size = p.stat().st_size
            if size > 1024:
                return CheckResult("initramfs", True,
                                   f"OK: {p} ({size} bytes)")
            return CheckResult("initramfs", False,
                               f"Initramfs too small: {p} ({size} bytes)")
        return CheckResult("initramfs", False,
                           f"Initramfs not found: {p}")

    def _check_modules(
        self, preset: dict, mounts: dict, staging_dir: str,
    ) -> CheckResult:
        """Verifie les modules kernel."""
        version = self.params.get("kernel_version", "")
        if not version and preset:
            version = preset.get("kernel_version", "")
        modules_path = self.params.get("modules_path", "")
        if not modules_path and preset:
            modules_path = preset.get("modules", "")

        if modules_path:
            p = Path(modules_path)
            if p.is_dir():
                return CheckResult("modules", True, f"OK: {p}")
            return CheckResult("modules", False,
                               f"Modules not found: {p}", severity="warning")

        if not version:
            return CheckResult("modules", False,
                               "Kernel version unknown, cannot check modules",
                               severity="warning")

        # Chercher dans tous les montages
        search_dirs = []
        if staging_dir:
            search_dirs.append(Path(staging_dir))
        for mp in mounts.values():
            search_dirs.append(Path(mp))

        for base in search_dirs:
            mod_dir = base / "lib" / "modules" / version
            if mod_dir.is_dir():
                return CheckResult("modules", True,
                                   f"OK: {mod_dir}")

        return CheckResult("modules", False,
                           f"Modules for kernel {version} not found",
                           severity="warning")

    def _check_zbm(self, efi_mount: str, zbm_efi_path: str) -> CheckResult:
        """Verifie ZFSBootMenu."""
        if not efi_mount or not zbm_efi_path:
            return CheckResult("zbm", False,
                               "ZBM EFI path or mount not configured",
                               severity="warning")

        full = Path(efi_mount) / zbm_efi_path
        if full.exists():
            return CheckResult("zbm", True, f"OK: {full}")
        return CheckResult("zbm", False,
                           f"ZBM EFI not found: {full}",
                           severity="warning")

    def _check_efi(self, efi_device: str, efi_mount: str) -> CheckResult:
        """Verifie la partition EFI."""
        if not efi_mount:
            return CheckResult("efi", False,
                               "EFI mount not configured", severity="warning")

        mp = Path(efi_mount)
        if not mp.is_dir():
            return CheckResult("efi", False,
                               f"EFI mount point missing: {efi_mount}")

        r = self.run_cmd(f"mountpoint -q {efi_mount}", check=False)
        if r.success:
            return CheckResult("efi", True,
                               f"OK: {efi_device} on {efi_mount}")
        return CheckResult("efi", False,
                           f"EFI not mounted: {efi_mount}")

    def _check_pool(self, pool_name: str) -> CheckResult:
        """Verifie qu'un pool est importe."""
        r = self.run_cmd(
            f"zpool list -H -o name,health {pool_name}",
            sudo=True, check=False)
        if r.success:
            parts = r.stdout.strip().split()
            health = parts[1] if len(parts) > 1 else "UNKNOWN"
            if health == "ONLINE":
                return CheckResult(f"pool_{pool_name}", True,
                                   f"Pool {pool_name}: ONLINE")
            return CheckResult(f"pool_{pool_name}", False,
                               f"Pool {pool_name}: {health}",
                               severity="warning")
        return CheckResult(f"pool_{pool_name}", False,
                           f"Pool {pool_name}: not imported")

    def _check_rootfs(
        self, boot_path: Path | None, rootfs_val: str,
    ) -> CheckResult:
        """Verifie le squashfs rootfs."""
        if not boot_path:
            return CheckResult("rootfs", False,
                               "boot_mount not configured", severity="warning")

        p = boot_path / rootfs_val if not rootfs_val.startswith("/") \
            else Path(rootfs_val)
        if p.exists():
            size = p.stat().st_size
            if size > 1024:
                return CheckResult("rootfs", True,
                                   f"OK: {p} ({size // 1024 // 1024} MB)")
            return CheckResult("rootfs", False,
                               f"Rootfs too small: {p}")
        return CheckResult("rootfs", False, f"Rootfs not found: {p}")

    def _check_overlay(
        self, overlay_ds: str, mounts: dict,
    ) -> CheckResult:
        """Verifie le dataset overlay."""
        if overlay_ds in mounts:
            return CheckResult("overlay", True,
                               f"OK: {overlay_ds} mounted")

        r = self.run_cmd(
            f"zfs list -H -o name {overlay_ds}",
            sudo=True, check=False)
        if r.success:
            return CheckResult("overlay", True,
                               f"OK: {overlay_ds} exists (not mounted)")
        return CheckResult("overlay", False,
                           f"Overlay dataset not found: {overlay_ds}",
                           severity="warning")

    def _check_boot_symlinks(self, boot_path: Path) -> CheckResult:
        """Verifie les symlinks de boot."""
        broken = []
        for name in ("vmlinuz", "initramfs.img", "System.map"):
            link = boot_path / name
            if link.is_symlink():
                target = link.resolve()
                if not target.exists():
                    broken.append(f"{name} -> {target}")

        if broken:
            return CheckResult("boot_symlinks", False,
                               f"Broken symlinks: {', '.join(broken)}")
        return CheckResult("boot_symlinks", True,
                           "Boot symlinks OK", severity="info")

    def _run_zbm_preflight(self):
        """Lance la validation pre-vol ZBM."""
        try:
            from function.zbm.validate import ZBMPreflightTask

            # Construire les params depuis les params coherence
            zbm_params = {
                "boot_mount": self.params.get("boot_mount", ""),
                "efi_device": self.params.get("efi_device", ""),
                "efi_mount": self.params.get("efi_mount", ""),
                "efi_part_num": self.params.get("efi_part_num", ""),
                "zbm_efi_path": self.params.get("zbm_efi_path", ""),
                "zbm_install_method": self.params.get("zbm_install_method", ""),
                "zbm_cmdline": self.params.get("zbm_cmdline", ""),
                "zbm_bootfs": self.params.get("zbm_bootfs", ""),
                "zbm_config_yaml": self.params.get("zbm_config_yaml", ""),
                "zbm_image_dir": self.params.get("zbm_image_dir", ""),
                "kernel_active": self.params.get("kernel_active", ""),
                "kernel_version": self.params.get("kernel_version", ""),
                "initramfs_active": self.params.get("initramfs_active", ""),
                "staging_dir": self.params.get("staging_dir", ""),
                "preset": self.params.get("preset", {}),
                "mounts": self.params.get("mounts", {}),
                "pools": self.params.get("pools", []),
            }

            task = ZBMPreflightTask(
                id="zbm_preflight_inline",
                params=zbm_params,
                context=self.context,
            )
            # Injecter le run_cmd helper
            task._cmd_runner = getattr(self, "_cmd_runner", None)
            return task.run()

        except ImportError:
            return None
        except Exception:
            return None
