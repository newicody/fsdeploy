# -*- coding: utf-8 -*-
"""
fsdeploy.function.zbm.validate
=================================
Validation pre-vol ZFSBootMenu.

Verifie AVANT installation que ZFSBootMenu fonctionnera correctement.
Toutes les verifications utilisent les paths de config/preset, aucun en dur.

Checks effectues :
  1. EFI : firmware UEFI present, partition EFI montee, ecriture possible
  2. Kernel : present, valide (magic bytes), taille non nulle
  3. Initramfs : present, valide (gzip/cpio/zstd), taille suffisante
  4. Symlinks : vmlinuz -> kernel, initramfs.img -> initramfs resolvent
  5. Modules ZFS : module zfs.ko present pour la version kernel
  6. Pool boot : importable, datasets accessibles
  7. Config ZBM : config.yaml valide (si generate-zbm)
  8. Outils : efibootmgr, dracut/mkinitcpio presents
  9. Espace disque : ESP a assez de place
 10. Coherence preset : toutes les references resolvent vers des fichiers reels
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource
from scheduler.security.decorator import security


# ===================================================================
# RESULT DATACLASSES
# ===================================================================

@dataclass
class ZBMCheck:
    """Resultat d'une verification individuelle."""
    name: str
    passed: bool
    message: str = ""
    severity: str = "error"  # error | warning | info
    details: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "OK" if self.passed else self.severity.upper()
        return f"[{status}] {self.name}: {self.message}"


@dataclass
class ZBMValidationReport:
    """Rapport complet de validation pre-vol ZBM."""
    checks: list[ZBMCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def errors(self) -> list[ZBMCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> list[ZBMCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    @property
    def infos(self) -> list[ZBMCheck]:
        return [c for c in self.checks if c.severity == "info"]

    def summary(self) -> str:
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c.passed)
        return (
            f"ZBM pre-flight: {ok}/{total} checks passed, "
            f"{len(self.errors)} errors, {len(self.warnings)} warnings"
        )

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "summary": self.summary(),
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "severity": c.severity,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "errors": [c.message for c in self.errors],
            "warnings": [c.message for c in self.warnings],
        }


# ===================================================================
# MAGIC BYTES VALIDATORS
# ===================================================================

def _check_file_magic(path: Path, expected: list[tuple[int, bytes, str]]) -> str:
    """
    Verifie les magic bytes d'un fichier.
    expected : [(offset, bytes, label), ...]
    Retourne le label du premier match ou "".
    """
    try:
        with path.open("rb") as f:
            header = f.read(0x210)
            for offset, magic, label in expected:
                end = offset + len(magic)
                if end <= len(header) and header[offset:end] == magic:
                    return label
    except (OSError, PermissionError):
        pass
    return ""


KERNEL_MAGICS = [
    (0, b"\x7fELF", "elf"),
    (0x202, b"HdrS", "bzImage"),
]

INITRAMFS_MAGICS = [
    (0, b"\x1f\x8b", "gzip"),
    (0, b"\x28\xb5\x2f\xfd", "zstd"),
    (0, b"\xfd\x37\x7a\x58\x5a\x00", "xz"),
    (0, b"070707", "cpio_odc"),
    (0, b"070701", "cpio_newc"),
    (0, b"070702", "cpio_crc"),
]


# ===================================================================
# TASK
# ===================================================================

@security.zbm.validate
class ZBMPreflightTask(Task):
    """
    Validation pre-vol ZFSBootMenu.

    Params attendus (tous depuis config/preset, aucun en dur) :
      - boot_mount: str         Point de montage boot (depuis pool.boot_mount)
      - efi_device: str         Device EFI (depuis partition.efi_device)
      - efi_mount: str          Point de montage EFI (depuis partition.efi_mount)
      - efi_part_num: str       Numero de partition EFI
      - zbm_efi_path: str       Chemin relatif du EFI ZBM (depuis zbm.efi_path)
      - zbm_install_method: str prebuilt | generate | manual
      - zbm_cmdline: str        Ligne de commande ZBM
      - zbm_bootfs: str         Dataset racine prefere
      - zbm_config_yaml: str    Chemin config.yaml (pour generate-zbm)
      - zbm_image_dir: str      Repertoire images ZBM
      - kernel_active: str      Nom du kernel actif (relatif a boot_mount)
      - kernel_version: str     Version kernel
      - initramfs_active: str   Nom de l'initramfs actif
      - staging_dir: str        Repertoire de staging kernel
      - preset: dict            Preset actif complet
      - mounts: dict            {dataset: mountpoint}
      - pools: list[str]        Pools requis
    """

    def run(self) -> ZBMValidationReport:
        report = ZBMValidationReport()

        # Extraire tous les params (ZERO valeur par defaut en dur)
        boot_mount = self.params.get("boot_mount", "")
        efi_device = self.params.get("efi_device", "")
        efi_mount = self.params.get("efi_mount", "")
        efi_part_num = self.params.get("efi_part_num", "")
        zbm_efi_path = self.params.get("zbm_efi_path", "")
        zbm_method = self.params.get("zbm_install_method", "")
        zbm_cmdline = self.params.get("zbm_cmdline", "")
        zbm_bootfs = self.params.get("zbm_bootfs", "")
        zbm_config_yaml = self.params.get("zbm_config_yaml", "")
        zbm_image_dir = self.params.get("zbm_image_dir", "")
        kernel_active = self.params.get("kernel_active", "")
        kernel_version = self.params.get("kernel_version", "")
        initramfs_active = self.params.get("initramfs_active", "")
        staging_dir = self.params.get("staging_dir", "") or boot_mount
        preset = self.params.get("preset", {})
        mounts = self.params.get("mounts", {})
        pools = self.params.get("pools", [])

        # ----------------------------------------------------------
        # 1. EFI FIRMWARE
        # ----------------------------------------------------------
        report.checks.append(self._check_efi_firmware())

        # ----------------------------------------------------------
        # 2. PARTITION EFI
        # ----------------------------------------------------------
        report.checks.append(self._check_efi_partition(
            efi_device, efi_mount))

        # ----------------------------------------------------------
        # 3. ESPACE DISQUE EFI
        # ----------------------------------------------------------
        if efi_mount:
            report.checks.append(self._check_efi_space(efi_mount))

        # ----------------------------------------------------------
        # 4. KERNEL
        # ----------------------------------------------------------
        report.checks.append(self._check_kernel(
            staging_dir, kernel_active, preset))

        # ----------------------------------------------------------
        # 5. INITRAMFS
        # ----------------------------------------------------------
        report.checks.append(self._check_initramfs(
            staging_dir, initramfs_active, preset))

        # ----------------------------------------------------------
        # 6. SYMLINKS
        # ----------------------------------------------------------
        if staging_dir:
            report.checks.append(self._check_symlinks(staging_dir))

        # ----------------------------------------------------------
        # 7. MODULES ZFS
        # ----------------------------------------------------------
        report.checks.append(self._check_zfs_module(
            kernel_version, staging_dir, mounts))

        # ----------------------------------------------------------
        # 8. POOLS
        # ----------------------------------------------------------
        for pool in pools:
            if pool:
                report.checks.append(self._check_pool(pool))

        # ----------------------------------------------------------
        # 9. ZBM EFI (si deja installe ou prebuilt)
        # ----------------------------------------------------------
        if zbm_efi_path and efi_mount:
            report.checks.append(self._check_zbm_efi(
                efi_mount, zbm_efi_path))

        # ----------------------------------------------------------
        # 10. OUTILS REQUIS
        # ----------------------------------------------------------
        report.checks.append(self._check_tools(zbm_method))

        # ----------------------------------------------------------
        # 11. EFIBOOTMGR
        # ----------------------------------------------------------
        if efi_device and efi_part_num:
            report.checks.append(self._check_efibootmgr(
                efi_device, efi_part_num, zbm_efi_path))

        # ----------------------------------------------------------
        # 12. CONFIG.YAML (si generate-zbm)
        # ----------------------------------------------------------
        if zbm_method == "generate" and zbm_config_yaml:
            report.checks.append(self._check_zbm_config_yaml(
                zbm_config_yaml))

        # ----------------------------------------------------------
        # 13. BOOTFS (zbm.prefer)
        # ----------------------------------------------------------
        if zbm_bootfs:
            report.checks.append(self._check_bootfs(zbm_bootfs))

        # ----------------------------------------------------------
        # 14. COHERENCE PRESET
        # ----------------------------------------------------------
        if preset:
            report.checks.append(self._check_preset_coherence(
                preset, staging_dir, mounts))

        return report

    # ===============================================================
    # INDIVIDUAL CHECKS
    # ===============================================================

    def _check_efi_firmware(self) -> ZBMCheck:
        """Verifie que le firmware UEFI est present."""
        efi_dir = Path("/sys/firmware/efi")
        if efi_dir.is_dir():
            return ZBMCheck("efi_firmware", True,
                            "UEFI firmware detected")
        return ZBMCheck("efi_firmware", False,
                        "UEFI firmware not detected (/sys/firmware/efi missing)",
                        severity="error")

    def _check_efi_partition(
        self, efi_device: str, efi_mount: str,
    ) -> ZBMCheck:
        """Verifie la partition EFI."""
        if not efi_device:
            return ZBMCheck("efi_partition", False,
                            "EFI device not configured (partition.efi_device)",
                            severity="error")
        if not efi_mount:
            return ZBMCheck("efi_partition", False,
                            "EFI mount not configured (partition.efi_mount)",
                            severity="error")

        mp = Path(efi_mount)
        if not mp.is_dir():
            return ZBMCheck("efi_partition", False,
                            f"EFI mount point does not exist: {efi_mount}",
                            severity="error")

        # Verifier que c'est monte
        r = self.run_cmd(f"mountpoint -q {efi_mount}", check=False)
        if not r.success:
            return ZBMCheck("efi_partition", False,
                            f"EFI partition not mounted at {efi_mount}",
                            severity="error",
                            details={"device": efi_device, "mount": efi_mount})

        # Verifier ecriture
        test_file = mp / ".fsdeploy_write_test"
        try:
            test_file.touch()
            test_file.unlink()
            writable = True
        except (OSError, PermissionError):
            writable = False

        if not writable:
            return ZBMCheck("efi_partition", False,
                            f"EFI partition not writable at {efi_mount}",
                            severity="error")

        return ZBMCheck("efi_partition", True,
                        f"EFI partition OK: {efi_device} on {efi_mount}",
                        details={"device": efi_device, "mount": efi_mount})

    def _check_efi_space(self, efi_mount: str) -> ZBMCheck:
        """Verifie l'espace disque sur l'ESP."""
        mp = Path(efi_mount)
        try:
            st = os.statvfs(str(mp))
            free_mb = (st.f_bavail * st.f_frsize) / (1024 * 1024)
            if free_mb < 10:
                return ZBMCheck("efi_space", False,
                                f"EFI partition low space: {free_mb:.1f} MB free",
                                severity="error",
                                details={"free_mb": round(free_mb, 1)})
            if free_mb < 50:
                return ZBMCheck("efi_space", True,
                                f"EFI partition space warning: {free_mb:.1f} MB free",
                                severity="warning",
                                details={"free_mb": round(free_mb, 1)})
            return ZBMCheck("efi_space", True,
                            f"EFI partition space OK: {free_mb:.1f} MB free",
                            severity="info",
                            details={"free_mb": round(free_mb, 1)})
        except OSError:
            return ZBMCheck("efi_space", False,
                            f"Cannot stat EFI partition: {efi_mount}",
                            severity="warning")

    def _check_kernel(
        self, staging_dir: str, kernel_active: str, preset: dict,
    ) -> ZBMCheck:
        """Verifie le kernel actif."""
        if not staging_dir:
            return ZBMCheck("kernel", False,
                            "staging_dir/boot_mount not configured",
                            severity="error")

        # Resoudre le kernel depuis preset ou config
        kernel_name = kernel_active
        if not kernel_name and preset:
            kernel_name = preset.get("kernel", "")

        if not kernel_name:
            return ZBMCheck("kernel", False,
                            "No active kernel configured "
                            "(kernel.active or preset.kernel)",
                            severity="error")

        sd = Path(staging_dir)
        kernel_path = sd / kernel_name if not kernel_name.startswith("/") \
            else Path(kernel_name)

        # Suivre les symlinks
        if kernel_path.is_symlink():
            resolved = kernel_path.resolve()
            if not resolved.exists():
                return ZBMCheck("kernel", False,
                                f"Kernel symlink broken: {kernel_path} -> {resolved}",
                                severity="error",
                                details={"path": str(kernel_path),
                                         "target": str(resolved)})
            kernel_path = resolved

        if not kernel_path.exists():
            return ZBMCheck("kernel", False,
                            f"Kernel not found: {kernel_path}",
                            severity="error")

        # Verifier taille
        size = kernel_path.stat().st_size
        if size < 1024:
            return ZBMCheck("kernel", False,
                            f"Kernel too small ({size} bytes): {kernel_path}",
                            severity="error")

        # Verifier magic bytes
        magic = _check_file_magic(kernel_path, KERNEL_MAGICS)
        if not magic:
            return ZBMCheck("kernel", False,
                            f"Kernel invalid magic bytes: {kernel_path}",
                            severity="error",
                            details={"path": str(kernel_path), "size": size})

        return ZBMCheck("kernel", True,
                        f"Kernel OK: {kernel_path.name} "
                        f"({size // 1024 // 1024} MB, {magic})",
                        details={"path": str(kernel_path), "size": size,
                                 "magic": magic})

    def _check_initramfs(
        self, staging_dir: str, initramfs_active: str, preset: dict,
    ) -> ZBMCheck:
        """Verifie l'initramfs actif."""
        if not staging_dir:
            return ZBMCheck("initramfs", False,
                            "staging_dir/boot_mount not configured",
                            severity="error")

        initramfs_name = initramfs_active
        if not initramfs_name and preset:
            initramfs_name = preset.get("initramfs", "")

        if not initramfs_name:
            return ZBMCheck("initramfs", False,
                            "No active initramfs configured "
                            "(initramfs.active or preset.initramfs)",
                            severity="error")

        sd = Path(staging_dir)
        ir_path = sd / initramfs_name if not initramfs_name.startswith("/") \
            else Path(initramfs_name)

        if ir_path.is_symlink():
            resolved = ir_path.resolve()
            if not resolved.exists():
                return ZBMCheck("initramfs", False,
                                f"Initramfs symlink broken: {ir_path} -> {resolved}",
                                severity="error")
            ir_path = resolved

        if not ir_path.exists():
            return ZBMCheck("initramfs", False,
                            f"Initramfs not found: {ir_path}",
                            severity="error")

        size = ir_path.stat().st_size
        if size < 1024:
            return ZBMCheck("initramfs", False,
                            f"Initramfs too small ({size} bytes): {ir_path}",
                            severity="error")

        magic = _check_file_magic(ir_path, INITRAMFS_MAGICS)
        if not magic:
            return ZBMCheck("initramfs", False,
                            f"Initramfs unknown format: {ir_path}",
                            severity="warning",
                            details={"path": str(ir_path), "size": size})

        return ZBMCheck("initramfs", True,
                        f"Initramfs OK: {ir_path.name} "
                        f"({size // 1024 // 1024} MB, {magic})",
                        details={"path": str(ir_path), "size": size,
                                 "magic": magic})

    def _check_symlinks(self, staging_dir: str) -> ZBMCheck:
        """Verifie que les symlinks de boot resolvent."""
        sd = Path(staging_dir)
        broken = []

        for name in ("vmlinuz", "initramfs.img", "System.map"):
            link = sd / name
            if link.is_symlink():
                target = link.resolve()
                if not target.exists():
                    broken.append(f"{name} -> {target} (BROKEN)")

        if broken:
            return ZBMCheck("symlinks", False,
                            f"Broken symlinks: {', '.join(broken)}",
                            severity="error",
                            details={"broken": broken})

        return ZBMCheck("symlinks", True,
                        "Boot symlinks OK",
                        severity="info")

    def _check_zfs_module(
        self, kernel_version: str, staging_dir: str, mounts: dict,
    ) -> ZBMCheck:
        """Verifie que le module ZFS est present pour le kernel."""
        if not kernel_version:
            return ZBMCheck("zfs_module", False,
                            "Kernel version unknown, cannot check ZFS module",
                            severity="warning")

        # Chercher dans staging_dir et dans tous les montages
        search_dirs = []
        if staging_dir:
            search_dirs.append(Path(staging_dir))
        for mp in mounts.values():
            search_dirs.append(Path(mp))

        for base in search_dirs:
            mod_dir = base / "lib" / "modules" / kernel_version
            if mod_dir.is_dir():
                # Chercher zfs.ko ou zfs.ko.zst etc
                for zfs_mod in mod_dir.rglob("zfs.ko*"):
                    return ZBMCheck("zfs_module", True,
                                    f"ZFS module found: {zfs_mod}",
                                    details={"path": str(zfs_mod),
                                             "version": kernel_version})

        # Verifier dans le systeme courant
        r = self.run_cmd(
            f"modinfo -k {kernel_version} zfs",
            check=False, sudo=False)
        if r.success:
            return ZBMCheck("zfs_module", True,
                            f"ZFS module available for kernel {kernel_version}",
                            severity="info")

        return ZBMCheck("zfs_module", False,
                        f"ZFS module not found for kernel {kernel_version}",
                        severity="error",
                        details={"version": kernel_version})

    def _check_pool(self, pool_name: str) -> ZBMCheck:
        """Verifie qu'un pool est importe et accessible."""
        r = self.run_cmd(
            f"zpool list -H -o name,health {pool_name}",
            sudo=True, check=False)
        if r.success:
            parts = r.stdout.strip().split()
            health = parts[1] if len(parts) > 1 else "UNKNOWN"
            if health == "ONLINE":
                return ZBMCheck(f"pool_{pool_name}", True,
                                f"Pool {pool_name}: ONLINE",
                                details={"health": health})
            return ZBMCheck(f"pool_{pool_name}", False,
                            f"Pool {pool_name}: {health}",
                            severity="warning",
                            details={"health": health})

        return ZBMCheck(f"pool_{pool_name}", False,
                        f"Pool {pool_name} not imported or not accessible",
                        severity="error")

    def _check_zbm_efi(
        self, efi_mount: str, zbm_efi_path: str,
    ) -> ZBMCheck:
        """Verifie que le fichier EFI ZBM existe."""
        full = Path(efi_mount) / zbm_efi_path
        if full.exists():
            size = full.stat().st_size
            return ZBMCheck("zbm_efi", True,
                            f"ZBM EFI found: {full} ({size // 1024} KB)",
                            details={"path": str(full), "size": size})
        return ZBMCheck("zbm_efi", False,
                        f"ZBM EFI not found: {full}",
                        severity="info",
                        details={"expected": str(full)})

    def _check_tools(self, zbm_method: str) -> ZBMCheck:
        """Verifie que les outils necessaires sont installes."""
        required = ["efibootmgr"]
        if zbm_method == "generate":
            required.extend(["generate-zbm", "dracut"])

        missing = []
        for tool in required:
            r = self.run_cmd(f"which {tool}", check=False)
            if not r.success:
                missing.append(tool)

        if missing:
            return ZBMCheck("tools", False,
                            f"Missing tools: {', '.join(missing)}",
                            severity="error",
                            details={"missing": missing})

        return ZBMCheck("tools", True,
                        f"Required tools present: {', '.join(required)}",
                        details={"tools": required})

    def _check_efibootmgr(
        self, efi_device: str, efi_part_num: str, zbm_efi_path: str,
    ) -> ZBMCheck:
        """Verifie la capacite a creer une entree EFI boot."""
        r = self.run_cmd("efibootmgr -v", sudo=True, check=False)
        if not r.success:
            return ZBMCheck("efibootmgr", False,
                            "efibootmgr cannot read EFI variables",
                            severity="error")

        # Extraire le disque depuis efi_device
        # Ex: /dev/nvme0n1p1 -> /dev/nvme0n1, part 1
        # Mais on ne presume rien : on utilise efi_device et efi_part_num
        details = {
            "device": efi_device,
            "part": efi_part_num,
            "zbm_path": zbm_efi_path,
        }

        # Verifier si une entree ZFSBootMenu existe deja
        if "ZFSBootMenu" in r.stdout:
            return ZBMCheck("efibootmgr", True,
                            "EFI boot entry 'ZFSBootMenu' already exists",
                            severity="info",
                            details=details)

        return ZBMCheck("efibootmgr", True,
                        "efibootmgr ready to create boot entry",
                        details=details)

    def _check_zbm_config_yaml(self, config_yaml: str) -> ZBMCheck:
        """Verifie le config.yaml pour generate-zbm."""
        p = Path(config_yaml)
        if not p.exists():
            return ZBMCheck("zbm_config", False,
                            f"ZBM config.yaml not found: {config_yaml}",
                            severity="error")
        try:
            import yaml
            with p.open() as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict):
                return ZBMCheck("zbm_config", False,
                                f"ZBM config.yaml invalid format: {config_yaml}",
                                severity="error")
            # Verifier les sections critiques
            has_global = "Global" in cfg
            has_components = "Components" in cfg or "EFI" in cfg
            if not has_global:
                return ZBMCheck("zbm_config", False,
                                "ZBM config.yaml missing 'Global' section",
                                severity="error")
            manage = cfg.get("Global", {}).get("ManageImages", False)
            if not manage:
                return ZBMCheck("zbm_config", False,
                                "ZBM config.yaml: ManageImages is not true",
                                severity="warning")
            return ZBMCheck("zbm_config", True,
                            f"ZBM config.yaml valid: {config_yaml}",
                            details={"sections": list(cfg.keys())})
        except ImportError:
            return ZBMCheck("zbm_config", False,
                            "PyYAML not installed, cannot validate config.yaml",
                            severity="warning")
        except Exception as exc:
            return ZBMCheck("zbm_config", False,
                            f"ZBM config.yaml parse error: {exc}",
                            severity="error")

    def _check_bootfs(self, bootfs: str) -> ZBMCheck:
        """Verifie que le dataset bootfs existe."""
        r = self.run_cmd(
            f"zfs list -H -o name {bootfs}",
            sudo=True, check=False)
        if r.success:
            return ZBMCheck("bootfs", True,
                            f"Boot dataset exists: {bootfs}")
        return ZBMCheck("bootfs", False,
                        f"Boot dataset not found: {bootfs}",
                        severity="error")

    def _check_preset_coherence(
        self, preset: dict, staging_dir: str, mounts: dict,
    ) -> ZBMCheck:
        """Verifie que toutes les references du preset resolvent."""
        sd = Path(staging_dir) if staging_dir else None
        missing = []

        for key in ("kernel", "initramfs"):
            val = preset.get(key, "")
            if not val:
                continue
            p = sd / val if sd and not val.startswith("/") else Path(val)
            # Suivre les symlinks
            if p.is_symlink():
                p = p.resolve()
            if not p.exists():
                missing.append(f"{key}={val} (not found at {p})")

        # Verifier rootfs (squashfs)
        rootfs_val = preset.get("rootfs", "")
        if rootfs_val:
            p = sd / rootfs_val if sd and not rootfs_val.startswith("/") \
                else Path(rootfs_val)
            if not p.exists():
                missing.append(f"rootfs={rootfs_val} (not found at {p})")

        # Verifier overlay dataset
        overlay_ds = preset.get("overlay_dataset", "")
        if overlay_ds and mounts:
            if overlay_ds not in mounts:
                # Verifier avec zfs list
                r = self.run_cmd(
                    f"zfs list -H -o name {overlay_ds}",
                    sudo=True, check=False)
                if not r.success:
                    missing.append(
                        f"overlay_dataset={overlay_ds} (not accessible)")

        if missing:
            return ZBMCheck("preset_coherence", False,
                            f"Preset references unresolved: "
                            f"{'; '.join(missing)}",
                            severity="error",
                            details={"missing": missing})

        return ZBMCheck("preset_coherence", True,
                        "Preset references all resolved")
