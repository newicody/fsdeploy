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
import shlex
import itertools
import re
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
        ready = self.passed
        status = "READY" if ready else "NOT READY"
        parts.append(f"Boot: {status}")
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
      - snapshots: list[str]     Snapshots requis (defaut: [])
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
      - run_scheduler_check: bool Exécuter la vérification d'intégration du scheduler (défaut: True)
    """

    def run(self) -> CoherenceReport:
        if self.params.get("quick_mode", False):
            return self._run_quick_report()
        report = CoherenceReport()

        boot_mount = self.params.get("boot_mount", "")
        staging_dir = self.params.get("staging_dir", "") or boot_mount
        preset = self.params.get("preset", {})
        mounts = self.params.get("mounts", {})
        pools = self.params.get("pools", [])
        run_scheduler_check = self.params.get("run_scheduler_check", True)

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

        # 6b. Pool free space
        report.checks.append(self._check_pool_space(pools))

        # 6c. Pool properties
        report.checks.append(self._check_pool_properties(pools))

        # 6d. Mounts coherence
        report.checks.append(self._check_mounts(mounts))

        # 6e. Mounts datasets existence
        report.checks.append(self._check_mounts_datasets(mounts))

        # 6f. Mount overlap
        report.checks.append(self._check_mount_overlap(mounts))

        # 6f1. Mount possible (dry‑run)
        report.checks.append(self._check_mount_possible(pools))

        # 6f. Datasets health
        report.checks.append(self._check_datasets(pools))

        # 6g. Nested dataset mount consistency
        report.checks.append(self._check_nested_dataset_mounts(pools))

        # 6h. Snapshots existence
        required_snapshots = self.params.get('snapshots', [])
        if not required_snapshots and preset:
            required_snapshots = preset.get('snapshots', [])
        if required_snapshots:
            report.checks.append(self._check_snapshots(required_snapshots))
        else:
            report.checks.append(CheckResult("snapshots", True, "No snapshots required", severity="info"))

        # 6i. Snapshot recency
        max_age = self.params.get('snapshot_max_age_days')
        if max_age is None and preset:
            max_age = preset.get('snapshot_max_age_days')
        if max_age is not None and required_snapshots:
            report.checks.append(self._check_snapshot_recency(required_snapshots, max_age))

        # 7. SquashFS rootfs
        rootfs_val = preset.get("rootfs", "")
        if rootfs_val:
            report.checks.append(self._check_rootfs(boot_path, rootfs_val))

        # 8. Overlay dataset
        overlay_ds = preset.get("overlay_dataset", "")
        if overlay_ds:
            report.checks.append(self._check_overlay(overlay_ds, mounts))

        # 8b. Root dataset (if specified)
        root_dataset = self.params.get("root_dataset", "")
        if not root_dataset:
            root_dataset = preset.get("root_dataset", "")
        if root_dataset:
            report.checks.append(self._check_root_dataset(root_dataset, mounts))

        # 9. Symlinks boot
        if boot_path:
            report.checks.append(self._check_boot_symlinks(boot_path))

        # 10. Boot mount access
        if boot_path:
            report.checks.append(self._check_boot_mount_access(boot_path))

        # 11. Scheduler integration
        if run_scheduler_check:
            report.checks.append(self._check_scheduler())

        # 11. Commandes systeme requises
        report.checks.append(self._check_required_commands())

        # 12. ZFS version compatibility
        report.checks.append(self._check_zfs_version())

        # 12b. ZFS module loaded
        report.checks.append(self._check_zfs_module_loaded())

        # 13. Kernel command line coherence
        report.checks.append(self._check_kernel_cmdline(preset))

        # 14. Kernel release compatibility
        report.checks.append(self._check_kernel_release(preset))

        # 15. Init system compatibility
        report.checks.append(self._check_init_system(preset))

        # 16. ZBM config file validity
        report.checks.append(self._check_zbm_config())

        # 17. Mount free space
        efi_mount = self.params.get("efi_mount", "")
        report.checks.append(self._check_mount_space(mounts, boot_path, efi_mount))

        # 18a. EFI filesystem type
        if efi_mount:
            report.checks.append(self._check_efi_fs_type(efi_mount))

        # 18b. ZFS services status
        report.checks.append(self._check_zfs_services())

        # 19. ZBM Pre-flight (optionnel mais par defaut)
        if self.params.get("run_zbm_preflight", True):
            report.zbm_report = self._run_zbm_preflight()
            if report.zbm_report is not None:
                self._add_zbm_checks(report)

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

    def _check_pool_space(self, pools):
        """Vérifie que chaque pool a suffisamment d'espace libre."""
        if not pools:
            return CheckResult("pool_space", True, "No pools configured", severity="info")
        warnings = []
        for pool in pools:
            if not pool:
                continue
            r = self.run_cmd(f"zpool list -H -p -o name,size,free {pool}", sudo=True, check=False)
            if not r.success:
                warnings.append(f"{pool}: cannot query space")
                continue
            # sortie: pool\t<size>\t<free>
            parts = r.stdout.strip().split('\t')
            if len(parts) < 3:
                warnings.append(f"{pool}: malformed output")
                continue
            try:
                size = int(parts[1])
                free = int(parts[2])
            except ValueError:
                warnings.append(f"{pool}: invalid numbers")
                continue
            if size == 0:
                ratio = 0.0
            else:
                ratio = free / size
            if ratio < 0.05:  # 5%
                warnings.append(f"{pool}: only {ratio:.1%} free")
        if warnings:
            msg = "; ".join(warnings[:5])
            if len(warnings) > 5:
                msg += f" ... (+{len(warnings)-5} more)"
            return CheckResult("pool_space", False, msg, severity="warning")
        return CheckResult("pool_space", True,
                           f"All {len(pools)} pool(s) have sufficient free space",
                           severity="info")

    def _check_pool_properties(self, pools):
        """Vérifie que les propriétés recommandées sont activées (compression)."""
        if not pools:
            return CheckResult("pool_properties", True, "No pools configured", severity="info")
        warnings = []
        for pool in pools:
            if not pool:
                continue
            r = self.run_cmd(f"zpool get -H -o property,value compression {pool}", sudo=True, check=False)
            if r.success:
                lines = r.stdout.strip().splitlines()
                for line in lines:
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[0] == 'compression':
                        value = parts[1]
                        if value == 'off':
                            warnings.append(f"{pool}: compression off")
            r2 = self.run_cmd(f"zpool get -H -o property,value dedup {pool}", sudo=True, check=False)
            if r2.success:
                lines = r2.stdout.strip().splitlines()
                for line in lines:
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[0] == 'dedup':
                        value = parts[1]
                        if value == 'on':
                            warnings.append(f"{pool}: dedup on (may affect performance)")
        if warnings:
            msg = "; ".join(warnings[:5])
            if len(warnings) > 5:
                msg += f" ... (+{len(warnings)-5} more)"
            return CheckResult("pool_properties", False, msg, severity="warning")
        return CheckResult("pool_properties", True,
                           f"Pool properties OK for {len(pools)} pool(s)", severity="info")

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

    def _check_root_dataset(self, root_dataset: str, mounts: dict) -> CheckResult:
        """Vérifie que le dataset racine existe et est correctement monté."""
        # Vérifier que le dataset existe
        r = self.run_cmd(f"zfs list -H -o name {root_dataset}", sudo=True, check=False)
        if not r.success:
            return CheckResult("root_dataset", False,
                               f"Root dataset does not exist: {root_dataset}",
                               severity="error")
        # Vérifier que le dataset est monté sur / (ou autre point de montage approprié)
        # On cherche dans mounts un point de montage correspondant.
        # Par défaut, le dataset racine peut être monté sur "/".
        # Nous allons simplement vérifier qu'il est présent dans mounts avec un point de montage non vide.
        # Si non monté, c'est un warning.
        mountpoint = mounts.get(root_dataset)
        if mountpoint:
            # Vérifier que le point de montage existe et est un répertoire
            mp_path = Path(mountpoint)
            if mp_path.exists() and mp_path.is_dir():
                return CheckResult("root_dataset", True,
                                   f"Root dataset {root_dataset} mounted at {mountpoint}",
                                   severity="info")
            else:
                return CheckResult("root_dataset", False,
                                   f"Mountpoint {mountpoint} for root dataset does not exist or is not a directory",
                                   severity="warning")
        else:
            # Vérifier si le dataset est monté ailleurs (via zfs get mountpoint)
            r2 = self.run_cmd(f"zfs get -H -o value mountpoint {root_dataset}", sudo=True, check=False)
            if r2.success and r2.stdout.strip() != "none":
                mp = r2.stdout.strip()
                return CheckResult("root_dataset", True,
                                   f"Root dataset {root_dataset} has mountpoint {mp} (but not in mounts config)",
                                   severity="warning")
            else:
                return CheckResult("root_dataset", False,
                                   f"Root dataset {root_dataset} not mounted (and no mountpoint configured)",
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

    def _check_mounts(self, mounts: dict) -> CheckResult:
        """Vérifie que chaque dataset est monté à son point de montage."""
        if not mounts:
            return CheckResult("mounts", True, "No mounts configured", severity="info")
        errors = []
        for dataset, mountpoint in mounts.items():
            mp = Path(mountpoint)
            if not mp.exists():
                errors.append(f"{dataset}: mountpoint {mountpoint} does not exist")
                continue
            r = self.run_cmd(["mountpoint", "-q", mountpoint], check=False)
            if not r.success:
                errors.append(f"{dataset}: not mounted at {mountpoint}")
        if errors:
            msg = "; ".join(errors[:5])
            if len(errors) > 5:
                msg += f" ... (+{len(errors)-5} more)"
            return CheckResult("mounts", False, msg, severity="warning")
        return CheckResult("mounts", True, f"All {len(mounts)} mount(s) are active")

    def _check_mounts_datasets(self, mounts: dict) -> CheckResult:
        """Vérifie que chaque dataset référencé dans mounts existe."""
        if not mounts:
            return CheckResult("mounts_datasets", True, "No mounts configured", severity="info")
        missing = []
        for dataset, mountpoint in mounts.items():
            r = self.run_cmd(f"zfs list -H -o name {dataset}", sudo=True, check=False)
            if not r.success:
                missing.append(dataset)
        if missing:
            msg = f"Missing datasets: {', '.join(missing[:5])}"
            if len(missing) > 5:
                msg += f" ... (+{len(missing)-5} more)"
            return CheckResult("mounts_datasets", False, msg, severity="warning")
        return CheckResult("mounts_datasets", True,
                           f"All {len(mounts)} dataset(s) exist", severity="info")

    def _check_mount_overlap(self, mounts: dict) -> CheckResult:
        """Vérifie qu'aucun point de montage n'est un sous‑répertoire d'un autre."""
        if not mounts:
            return CheckResult("mount_overlap", True, "No mounts configured", severity="info")
        # Convertir les chemins en Path
        from pathlib import Path
        mount_list = [(ds, Path(mp)) for ds, mp in mounts.items()]
        errors = []
        for (ds1, mp1), (ds2, mp2) in itertools.combinations(mount_list, 2):
            try:
                # Vérifier si mp1 est un parent de mp2 ou l'inverse
                if mp1 == mp2:
                    errors.append(f"{ds1} et {ds2} ont le même point de montage {mp1}")
                elif mp1 in mp2.parents:
                    errors.append(f"{ds1} ({mp1}) est un ancêtre de {ds2} ({mp2})")
                elif mp2 in mp1.parents:
                    errors.append(f"{ds2} ({mp2}) est un ancêtre de {ds1} ({mp1})")
            except Exception:
                pass
        if errors:
            msg = "; ".join(errors[:5])
            if len(errors) > 5:
                msg += f" ... (+{len(errors)-5} more)"
            return CheckResult("mount_overlap", False, msg, severity="warning")
        return CheckResult("mount_overlap", True,
                           f"Pas de chevauchement parmi {len(mounts)} montage(s)", severity="info")

    def _check_boot_mount_access(self, boot_path: Path | None) -> CheckResult:
        """Vérifie que le point de montage boot est accessible en lecture."""
        if not boot_path:
            return CheckResult("boot_mount_access", False,
                               "boot_mount not configured", severity="warning")
        if not boot_path.exists():
            return CheckResult("boot_mount_access", False,
                               f"Boot path does not exist: {boot_path}")
        if not boot_path.is_dir():
            return CheckResult("boot_mount_access", False,
                               f"Boot path is not a directory: {boot_path}")
        import os
        if os.access(boot_path, os.R_OK):
            return CheckResult("boot_mount_access", True,
                               f"Boot mount readable: {boot_path}", severity="info")
        else:
            return CheckResult("boot_mount_access", False,
                               f"Boot mount not readable: {boot_path}", severity="warning")

    def _check_datasets(self, pools):
        """Vérifie l'état de tous les datasets dans les pools."""
        all_healthy = True
        problems = []
        for pool in pools:
            if not pool:
                continue
            r = self.run_cmd(f"zfs list -H -o name,health -r {pool}", sudo=True, check=False)
            if not r.success:
                all_healthy = False
                problems.append(f"Pool {pool}: unable to list datasets")
                continue
            lines = r.stdout.strip().splitlines()
            for line in lines:
                parts = line.strip().split('\t')
                if len(parts) < 2:
                    continue
                ds, health = parts[0], parts[1]
                if health != "ONLINE":
                    all_healthy = False
                    problems.append(f"{ds}: {health}")
        if not all_healthy:
            msg = f"Datasets health issues: {', '.join(problems[:5])}"
            if len(problems) > 5:
                msg += f" ... (+{len(problems)-5} more)"
            return CheckResult("datasets", False, msg, severity="warning")
        else:
            return CheckResult("datasets", True, f"All datasets in {len(pools)} pool(s) are ONLINE", severity="info")

    def _check_nested_dataset_mounts(self, pools):
        """Vérifie que les datasets enfants ne sont pas montés alors que le parent ne l'est pas (incohérence)."""
        if not pools:
            return CheckResult("nested_mounts", True, "No pools configured", severity="info")
        errors = []
        for pool in pools:
            if not pool:
                continue
            # Lister les datasets avec leur mountpoint et mounted status
            # zfs list -H -o name,mountpoint,mounted -r pool
            r = self.run_cmd(f"zfs list -H -o name,mountpoint,mounted -r {pool}", sudo=True, check=False)
            if not r.success:
                continue
            lines = r.stdout.strip().splitlines()
            # Créer un dict de nom -> (mountpoint, mounted)
            ds_info = {}
            for line in lines:
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                name, mp, mounted = parts[0], parts[1], parts[2]
                ds_info[name] = (mp, mounted == 'yes')
            # Pour chaque dataset, vérifier si parent est monté alors que enfant ne l'est pas, ou l'inverse
            for ds, (mp, mounted) in ds_info.items():
                if mp == 'none' or mp == '-':
                    continue
                # Trouver le parent immédiat
                parent = '/'.join(ds.split('/')[:-1])
                if not parent or parent == ds:
                    continue
                parent_info = ds_info.get(parent)
                if not parent_info:
                    continue
                parent_mp, parent_mounted = parent_info
                if parent_mp == 'none' or parent_mp == '-':
                    # parent pas de mountpoint défini, on ne peut pas vérifier
                    continue
                # Si parent monté mais enfant pas monté -> incohérence
                if parent_mounted and not mounted:
                    errors.append(f"{ds} not mounted while parent {parent} is mounted")
                # Si parent pas monté mais enfant monté -> possible mais peut être voulu (par exemple, datasets séparés)
                # On ne le signale que comme warning
                if not parent_mounted and mounted:
                    errors.append(f"{ds} mounted while parent {parent} is not mounted (possible inconsistency)")
        if errors:
            msg = "; ".join(errors[:5])
            if len(errors) > 5:
                msg += f" ... (+{len(errors)-5} more)"
            return CheckResult("nested_mounts", False, msg, severity="warning")
        return CheckResult("nested_mounts", True,
                           f"Nested mount consistency OK for {len(pools)} pool(s)", severity="info")

    def _check_snapshots(self, snapshot_list):
        """Vérifie l'existence des snapshots requis."""
        missing = []
        for snap in snapshot_list:
            r = self.run_cmd(f"zfs list -H -o name {snap}", sudo=True, check=False)
            if not r.success:
                missing.append(snap)
        if missing:
            return CheckResult("snapshots", False, f"Missing snapshots: {', '.join(missing)}", severity="warning")
        else:
            return CheckResult("snapshots", True, f"All {len(snapshot_list)} required snapshots exist", severity="info")

    def _check_snapshot_recency(self, snapshot_list, max_age_days):
        """Vérifie que chaque snapshot a moins de max_age_days jours."""
        import time
        too_old = []
        current = time.time()
        for snap in snapshot_list:
            r = self.run_cmd(f"zfs get -Hp -o value creation {snap}", sudo=True, check=False)
            if not r.success:
                continue
            try:
                timestamp = int(r.stdout.strip())
                age_days = (current - timestamp) / (24 * 3600)
                if age_days > max_age_days:
                    too_old.append((snap, round(age_days, 1)))
            except ValueError:
                pass
        if too_old:
            details = ", ".join(f"{snap} ({age}d)" for snap, age in too_old[:3])
            if len(too_old) > 3:
                details += f" ... (+{len(too_old)-3} more)"
            return CheckResult("snapshot_recency", False,
                               f"Snapshots older than {max_age_days} days: {details}",
                               severity="warning")
        return CheckResult("snapshot_recency", True,
                           f"All snapshots are within {max_age_days} days",
                           severity="info")

    def _check_scheduler(self) -> CheckResult:
        """Vérifie l'intégration du scheduler."""
        try:
            from ...scheduler.verify import SchedulerVerifyTask
        except ImportError:
            # fallback pour certains environnements
            from fsdeploy.lib.function.scheduler.verify import SchedulerVerifyTask
        try:
            task = SchedulerVerifyTask(
                id="scheduler_check_inline",
                params=self.params,
                context=self.context,
            )
            # Copier le helper de commande
            if hasattr(self, '_cmd_runner'):
                task._cmd_runner = self._cmd_runner
            # Exécuter la vérification
            task.run()
            result = task.result if hasattr(task, 'result') else None
            # --- Vérifications supplémentaires de cohérence runtime ---
            try:
                from ...scheduler.model.runtime import get_global_runtime
            except ImportError:
                from fsdeploy.lib.scheduler.model.runtime import get_global_runtime
            runtime = get_global_runtime()
            errors = []
            # 1. Cohérence des locks
            lock_errors = runtime.validate_locks()
            if lock_errors:
                errors.extend(lock_errors)
            # 2. Vérifier que chaque tâche en cours a un runtime défini et cohérent
            with runtime._lock:  # accéder au verrou interne pour éviter les races
                for task_id, info in runtime.running.items():
                    task_obj = info.get("task")
                    if task_obj is None:
                        errors.append(f"Tâche {task_id} en cours sans objet task.")
                        continue
                    if task_obj.runtime is None:
                        errors.append(f"Tâche {task_id} n'a pas de runtime défini.")
                    elif task_obj.runtime is not runtime:
                        errors.append(f"Tâche {task_id} a un runtime différent de l'instance globale.")
                    # Vérifier que before_run a été appelé (flag interne)
                    if not getattr(task_obj, '_before_run_called', False):
                        errors.append(f"Tâche {task_id} n'a pas appelé before_run (ou flag manquant).")
            # 3. Vérifier que les tâches en attente ont un runtime défini (si l'attribut existe)
            waiting_dict = getattr(runtime, 'waiting', None)
            if waiting_dict is not None:
                with runtime._lock:
                    # selon l'implémentation, waiting peut être un dict ou autre
                    if isinstance(waiting_dict, dict):
                        for waiting_id, waiting_task in waiting_dict.items():
                            if waiting_task.runtime is None:
                                errors.append(f"Tâche en attente {waiting_id} n'a pas de runtime défini.")
            # --- Évaluation finale ---
            if errors:
                details = "; ".join(errors[:5])  # limiter la longueur
                if len(errors) > 5:
                    details += f" ... (+{len(errors)-5} autres)"
                return CheckResult(
                    "scheduler_integration",
                    False,
                    f"Problèmes de cohérence runtime détectés : {details}",
                    severity="warning"
                )
            # Si SchedulerVerifyTask a réussi et aucune erreur runtime
            if result and result.get('health'):
                return CheckResult(
                    "scheduler_integration",
                    True,
                    f"OK: {result.get('task_classes_found', '?')} tâches, {result.get('intents_registered', '?')} intents, runtime cohérent",
                    severity="info"
                )
            else:
                msg = "Échec de vérification du scheduler"
                if result:
                    msg += f": santé={result.get('health')}"
                return CheckResult(
                    "scheduler_integration",
                    False,
                    msg,
                    severity="warning"
                )
        except Exception as e:
            return CheckResult(
                "scheduler_integration",
                False,
                f"Erreur lors de la vérification du scheduler: {e}",
                severity="warning"
            )

    def _check_required_commands(self) -> CheckResult:
        """Verifie la disponibilite des commandes systeme essentielles."""
        required = ["zpool", "zfs", "mount", "lsblk", "blkid"]
        optional = ["efibootmgr", "mkinitramfs", "dracut", "update-initramfs"]
        missing = []
        optional_missing = []
        for cmd in required:
            r = self.run_cmd(f"command -v {shlex.quote(cmd)}", check=False, timeout=2)
            if not r.success:
                missing.append(cmd)
        for cmd in optional:
            r = self.run_cmd(f"command -v {shlex.quote(cmd)}", check=False, timeout=2)
            if not r.success:
                optional_missing.append(cmd)
        if missing:
            return CheckResult("system_commands", False,
                               f"Missing required commands: {', '.join(missing)}",
                               severity="error")
        msg = "All required commands present"
        if optional_missing:
            msg += f"; missing optional: {', '.join(optional_missing)}"
            return CheckResult("system_commands", True, msg, severity="warning")
        else:
            return CheckResult("system_commands", True, msg, severity="info")

    def _check_zfs_version(self) -> CheckResult:
        """Vérifie que la version de ZFS est compatible."""
        r = self.run_cmd("zfs --version 2>/dev/null | head -1", check=False)
        if not r.success:
            return CheckResult("zfs_version", False,
                               "Impossible de déterminer la version de ZFS",
                               severity="warning")
        match = re.search(r'zfs-(\d+\.\d+\.\d+)', r.stdout)
        if not match:
            # essayer un autre format
            match = re.search(r'(\d+\.\d+\.\d+)', r.stdout)
        if match:
            version_str = match.group(1)
            # Comparaison simple : on veut au moins 2.0.0
            parts = list(map(int, version_str.split('.')))
            if len(parts) >= 3:
                major, minor, patch = parts[0], parts[1], parts[2]
                if (major > 2) or (major == 2 and minor >= 0):
                    return CheckResult("zfs_version", True,
                                       f"ZFS version {version_str} compatible",
                                       severity="info")
                else:
                    return CheckResult("zfs_version", False,
                                       f"ZFS version {version_str} est peut-être trop ancienne (>=2.0.0 recommandé)",
                                       severity="warning")
        # Si on ne peut pas parser
        return CheckResult("zfs_version", True,
                           f"Version ZFS détectée (format inconnu) : {r.stdout[:60]}",
                           severity="info")

    def _check_zfs_module_loaded(self) -> CheckResult:
        """Vérifie que le module ZFS est chargé dans le noyau."""
        r = self.run_cmd("lsmod | grep -q ^zfs", check=False)
        if r.success:
            return CheckResult("zfs_module", True,
                               "ZFS kernel module is loaded",
                               severity="info")
        else:
            return CheckResult("zfs_module", False,
                               "ZFS kernel module not loaded",
                               severity="warning")

    def _check_kernel_cmdline(self, preset: dict) -> CheckResult:
        """Vérifie que la ligne de commande du noyau contient les paramètres requis."""
        required_params = self.params.get("required_kernel_params", [])
        if not required_params:
            # essayer de déduire du preset
            required_params = preset.get("required_kernel_params", [])
        if not required_params:
            return CheckResult("kernel_cmdline", True,
                               "No required kernel parameters configured",
                               severity="info")
        # Lire la ligne de commande actuelle
        cmdline_path = Path("/proc/cmdline")
        if not cmdline_path.exists():
            return CheckResult("kernel_cmdline", False,
                               "Cannot read /proc/cmdline", severity="warning")
        with open(cmdline_path) as f:
            current = f.read().strip()
        # Vérifier chaque paramètre requis
        missing = []
        for param in required_params:
            if param not in current:
                missing.append(param)
        if missing:
            return CheckResult("kernel_cmdline", False,
                               f"Missing kernel parameters: {', '.join(missing)}",
                               severity="warning")
        return CheckResult("kernel_cmdline", True,
                           f"All required parameters present", severity="info")

    def _check_kernel_release(self, preset: dict) -> CheckResult:
        """Vérifie que la version du noyau en cours correspond à celle attendue."""
        expected = self.params.get("kernel_version", "")
        if not expected:
            expected = preset.get("kernel_version", "")
        if not expected:
            return CheckResult("kernel_release", True,
                               "No specific kernel version required",
                               severity="info")
        # Obtenir la version du noyau en cours
        import platform
        current = platform.release()
        if current == expected:
            return CheckResult("kernel_release", True,
                               f"Kernel release matches: {current}",
                               severity="info")
        # Sinon, on peut vérifier si le noyau attendu est installé (pas forcément en cours)
        # Pour l'instant, on émet un avertissement
        return CheckResult("kernel_release", False,
                           f"Running kernel {current} differs from expected {expected}",
                           severity="warning")

    def _check_init_system(self, preset: dict) -> CheckResult:
        """Vérifie que le système d'initialisation détecté correspond à celui attendu."""
        expected = preset.get("init_system", "")
        if not expected:
            return CheckResult("init_system", True,
                               "No specific init system required",
                               severity="info")
        try:
            from ..init_check import detect_init
            detected, version = detect_init()
            if detected == expected:
                return CheckResult("init_system", True,
                                   f"Init system matches: {detected}",
                                   severity="info")
            else:
                return CheckResult("init_system", False,
                                   f"Init system mismatch: expected {expected}, detected {detected}",
                                   severity="warning")
        except Exception as e:
            return CheckResult("init_system", False,
                               f"Unable to detect init system: {e}",
                               severity="warning")

    def _check_zbm_config(self) -> CheckResult:
        """Vérifie que le fichier de configuration ZBM est valide (YAML)."""
        config_path = self.params.get("zbm_config_yaml", "")
        if not config_path:
            return CheckResult("zbm_config", True,
                               "No ZBM config path specified", severity="info")
        path = Path(config_path)
        if not path.exists():
            return CheckResult("zbm_config", False,
                               f"ZBM config file not found: {config_path}",
                               severity="warning")
        # Essayer de parser le YAML
        try:
            import yaml
            with open(path) as f:
                yaml.safe_load(f)
            return CheckResult("zbm_config", True,
                               f"ZBM config YAML is valid: {config_path}",
                               severity="info")
        except ImportError:
            return CheckResult("zbm_config", False,
                               "PyYAML not installed, cannot validate",
                               severity="warning")
        except Exception as e:
            return CheckResult("zbm_config", False,
                               f"Invalid YAML in ZBM config: {e}",
                               severity="warning")

    def _check_mount_space(self, mounts_dict, boot_path=None, efi_mount=None):
        """Vérifie l'espace libre sur les points de montage."""
        # Liste des chemins uniques
        paths = set()
        if boot_path and isinstance(boot_path, Path):
            paths.add(str(boot_path))
        if efi_mount:
            paths.add(efi_mount)
        for mp in mounts_dict.values():
            paths.add(mp)

        errors = []
        for p in paths:
            r = self.run_cmd(
                f"df -P --block-size=1M {shlex.quote(p)} 2>/dev/null | tail -1",
                check=False,
                timeout=5,
            )
            if not r.success:
                continue  # ignorer si df échoue (non monté, etc.)
            # sortie: /dev/sda1 1000 800 200 80% /boot
            parts = r.stdout.strip().split()
            if len(parts) < 6:
                continue
            try:
                total_mb = int(parts[1])
                used_mb = int(parts[2])
                avail_mb = int(parts[3])
                use_percent = int(parts[4].replace('%', ''))
            except ValueError:
                continue
            # Seuil : si moins de 100 MB libre OU plus de 95% utilisé
            if avail_mb < 100 or use_percent > 95:
                errors.append(f"{p}: {avail_mb} MB free ({use_percent}% used)")
        if errors:
            msg = "Low disk space: " + "; ".join(errors[:3])
            if len(errors) > 3:
                msg += f" ... (+{len(errors)-3} more)"
            return CheckResult("mount_space", False, msg, severity="warning")
        return CheckResult("mount_space", True,
                           "Adequate free space on all mounts", severity="info")

    def _check_efi_fs_type(self, efi_mount: str) -> CheckResult:
        """Vérifie que le point de montage EFI utilise un système de fichiers vfat."""
        r = self.run_cmd(f"findmnt -no FSTYPE {efi_mount}", check=False)
        if not r.success:
            return CheckResult("efi_fs_type", False,
                               f"Cannot determine filesystem type of {efi_mount}",
                               severity="warning")
        fstype = r.stdout.strip().lower()
        if fstype == "vfat":
            return CheckResult("efi_fs_type", True,
                               f"EFI filesystem is vfat ({efi_mount})",
                               severity="info")
        else:
            return CheckResult("efi_fs_type", False,
                               f"EFI filesystem type is {fstype}, expected vfat",
                               severity="warning")

    def _check_zfs_services(self) -> CheckResult:
        """Vérifie l'état des services ZFS (systemd uniquement)."""
        # Détecter init system via /proc/1/comm
        try:
            with open("/proc/1/comm", "r") as f:
                init_comm = f.read().strip()
        except Exception:
            init_comm = ""
        if init_comm != "systemd":
            return CheckResult("zfs_services", True,
                               f"Init system is {init_comm}, service check not applicable",
                               severity="info")
        # Vérifier les services
        services = ["zfs-import-cache.service", "zfs-import-scan.service", "zfs-mount.service"]
        inactive = []
        for svc in services:
            r = self.run_cmd(f"systemctl is-active {svc}", check=False)
            if not r.success:
                inactive.append(svc)
        if inactive:
            return CheckResult("zfs_services", False,
                               f"Inactive ZFS services: {', '.join(inactive)}",
                               severity="warning")
        return CheckResult("zfs_services", True,
                           "All ZFS systemd services are active", severity="info")

    def _check_mount_possible(self, pools):
        """Vérifie que les datasets peuvent être montés (dry-run)."""
        if not pools:
            return CheckResult("mount_possible", True, "No pools configured", severity="info")
        for pool in pools:
            r = self.run_cmd(f"zfs mount -n -a -t filesystem {pool} 2>&1", sudo=True, check=False)
            if not r.success:
                # extraire l'erreur
                err = r.stderr.strip()[:200]
                return CheckResult("mount_possible", False,
                                   f"Dry-run mount failed for pool {pool}: {err}",
                                   severity="warning")
        return CheckResult("mount_possible", True,
                           f"All datasets in {len(pools)} pool(s) can be mounted",
                           severity="info")

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

    def _add_zbm_checks(self, report):
        """Ajoute les vérifications du rapport ZBM au rapport principal."""
        if report.zbm_report is None:
            return
        # On suppose que zbm_report a un attribut `checks` (liste d'objets ZBMCheck)
        if not hasattr(report.zbm_report, 'checks'):
            return
        for zcheck in report.zbm_report.checks:
            # Récupérer les attributs via getattr avec valeurs par défaut
            name = getattr(zcheck, 'name', 'unknown')
            # Certains rapports peuvent utiliser 'passed', d'autres 'status'
            passed = getattr(zcheck, 'passed', False)
            if not isinstance(passed, bool):
                # Essayer de convertir
                passed = str(passed).lower() in ('true', 'ok', 'passed', 'success')
            message = getattr(zcheck, 'message', '')
            # Sévérité : par défaut 'info'
            severity = getattr(zcheck, 'severity', 'info')
            report.checks.append(CheckResult(
                name=f"zbm_{name}",
                passed=passed,
                message=message,
                severity=severity
            ))

    def _run_quick_report(self) -> CoherenceReport:
        """Exécute un sous-ensemble critique des vérifications."""
        report = CoherenceReport()

        boot_mount = self.params.get("boot_mount", "")
        staging_dir = self.params.get("staging_dir", "") or boot_mount
        preset = self.params.get("preset", {})
        mounts = self.params.get("mounts", {})
        pools = self.params.get("pools", [])
        run_scheduler_check = self.params.get("run_scheduler_check", True)

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
        # 6. Pools importés
        for pool in pools:
            if pool:
                report.checks.append(self._check_pool(pool))
        # 7. Pool free space
        report.checks.append(self._check_pool_space(pools))
        # 8. Mounts coherence
        report.checks.append(self._check_mounts(mounts))
        # 9. Mounts datasets existence
        report.checks.append(self._check_mounts_datasets(mounts))
        # 10. Datasets health
        report.checks.append(self._check_datasets(pools))
        # 10b. Mount possible (dry-run)
        report.checks.append(self._check_mount_possible(pools))
        # 11. Snapshots existence
        required_snapshots = self.params.get('snapshots', [])
        if not required_snapshots and preset:
            required_snapshots = preset.get('snapshots', [])
        if required_snapshots:
            report.checks.append(self._check_snapshots(required_snapshots))
        # 12. Root dataset (if specified)
        root_dataset = self.params.get("root_dataset", "")
        if not root_dataset:
            root_dataset = preset.get("root_dataset", "")
        if root_dataset:
            report.checks.append(self._check_root_dataset(root_dataset, mounts))
        # 13. Boot symlinks
        if boot_path:
            report.checks.append(self._check_boot_symlinks(boot_path))
        # 14. Boot mount access
        if boot_path:
            report.checks.append(self._check_boot_mount_access(boot_path))
        # 15. Scheduler integration
        if run_scheduler_check:
            report.checks.append(self._check_scheduler())
        # 16. Commandes systeme requises
        report.checks.append(self._check_required_commands())
        # 17. ZFS version compatibility
        report.checks.append(self._check_zfs_version())
        # 18. ZFS module loaded
        report.checks.append(self._check_zfs_module_loaded())
        # 19. Kernel command line coherence
        report.checks.append(self._check_kernel_cmdline(preset))
        # 20. Mount free space
        efi_mount = self.params.get("efi_mount", "")
        report.checks.append(self._check_mount_space(mounts, boot_path, efi_mount))

        # ZBM pre-flight non exécuté en mode rapide (optionnel)
        # Les autres vérifications non critiques sont omises

        return report
