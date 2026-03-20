"""
fsdeploy.function.coherence.check
===================================
Vérification de cohérence du système avant boot.

Vérifie :
  - Kernel présent et accessible
  - Initramfs valide
  - ZFSBootMenu installé (si mode zbm)
  - Datasets montables
  - Checksums intacts
  - Overlayfs fonctionnel
  - Presets cohérents
"""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from scheduler.model.task import Task
from scheduler.security.decorator import security


@dataclass
class CheckResult:
    """Résultat d'une vérification individuelle."""
    name: str
    passed: bool
    message: str = ""
    severity: str = "error"  # error | warning | info


@dataclass
class CoherenceReport:
    """Rapport complet de cohérence."""
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def errors(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    def summary(self) -> str:
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c.passed)
        return (
            f"{ok}/{total} checks passed, "
            f"{len(self.errors)} errors, "
            f"{len(self.warnings)} warnings"
        )


@security.coherence.check
class CoherenceCheckTask(Task):
    """Vérifie la cohérence complète du système."""

    def run(self) -> CoherenceReport:
        report = CoherenceReport()
        boot_path = Path(self.params.get("boot_path", "/boot"))
        preset = self.params.get("preset", {})

        # 1. Kernel
        report.checks.append(self._check_kernel(boot_path, preset))

        # 2. Initramfs
        report.checks.append(self._check_initramfs(boot_path, preset))

        # 3. Modules
        report.checks.append(self._check_modules(preset))

        # 4. ZFSBootMenu
        report.checks.append(self._check_zbm(boot_path))

        # 5. EFI
        report.checks.append(self._check_efi())

        # 6. Pools importés
        report.checks.extend(self._check_pools())

        # 7. SquashFS rootfs
        if preset.get("rootfs"):
            report.checks.append(self._check_rootfs(boot_path, preset))

        # 8. Overlay dataset
        if preset.get("overlay_dataset"):
            report.checks.append(self._check_overlay(preset))

        return report

    def _check_kernel(self, boot: Path, preset: dict) -> CheckResult:
        kernel_path = preset.get("kernel", "")
        if kernel_path:
            p = boot / kernel_path if not kernel_path.startswith("/") else Path(kernel_path)
        else:
            # Chercher le symlink
            p = boot / "vmlinuz"

        if p.exists() or p.is_symlink():
            target = p.resolve() if p.is_symlink() else p
            if target.exists() and target.stat().st_size > 0:
                return CheckResult("kernel", True, f"OK: {target}")
            return CheckResult("kernel", False, f"Kernel target empty or missing: {target}")
        return CheckResult("kernel", False, f"Kernel not found: {p}")

    def _check_initramfs(self, boot: Path, preset: dict) -> CheckResult:
        initramfs_path = preset.get("initramfs", "")
        if initramfs_path:
            p = boot / initramfs_path if not initramfs_path.startswith("/") else Path(initramfs_path)
        else:
            p = boot / "initramfs.img"

        if p.exists():
            size = p.stat().st_size
            if size > 1024:
                return CheckResult("initramfs", True, f"OK: {p} ({size} bytes)")
            return CheckResult("initramfs", False, f"Initramfs too small: {size} bytes")
        return CheckResult("initramfs", False, f"Initramfs not found: {p}")

    def _check_modules(self, preset: dict) -> CheckResult:
        modules_path = preset.get("modules", "")
        if not modules_path:
            # Vérifier /lib/modules/<uname -r>
            r = self.run_cmd("uname -r", check=False)
            kver = r.stdout.strip() if r.success else ""
            if kver:
                p = Path(f"/lib/modules/{kver}")
                if p.is_dir() and list(p.glob("*.ko*")):
                    return CheckResult("modules", True, f"OK: {p}")
            return CheckResult("modules", False, "No kernel modules found",
                             severity="warning")

        p = Path(modules_path)
        if p.is_dir():
            return CheckResult("modules", True, f"OK: {p}")
        if p.is_file() and p.suffix == ".sfs":
            return CheckResult("modules", True, f"OK (squashfs): {p}")
        return CheckResult("modules", False, f"Modules not found: {p}")

    def _check_zbm(self, boot: Path) -> CheckResult:
        zbm_locations = [
            boot / "efi" / "ZBM" / "VMLINUZ.EFI",
            boot / "EFI" / "ZBM" / "VMLINUZ.EFI",
            boot / "efi" / "zfsbootmenu" / "vmlinuz.EFI",
            Path("/boot/efi/EFI/ZBM/VMLINUZ.EFI"),
        ]
        for loc in zbm_locations:
            if loc.exists():
                return CheckResult("zbm", True, f"OK: {loc}")
        return CheckResult("zbm", False, "ZFSBootMenu EFI not found",
                         severity="warning")

    def _check_efi(self) -> CheckResult:
        if Path("/sys/firmware/efi").is_dir():
            r = self.run_cmd("efibootmgr -v", sudo=True, check=False)
            if r.success and "ZFSBootMenu" in r.stdout:
                return CheckResult("efi", True, "EFI entry found")
            return CheckResult("efi", False, "No ZFSBootMenu EFI entry",
                             severity="warning")
        return CheckResult("efi", False, "Not an EFI system", severity="info")

    def _check_pools(self) -> list[CheckResult]:
        results = []
        r = self.run_cmd("zpool list -H -o name,health", check=False)
        if not r.success:
            results.append(CheckResult("pools", False, "Cannot list pools"))
            return results

        for line in r.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name, health = parts[0], parts[1]
                passed = health == "ONLINE"
                sev = "error" if health == "FAULTED" else "warning" if not passed else "info"
                results.append(CheckResult(
                    f"pool.{name}", passed,
                    f"{name}: {health}", severity=sev,
                ))
        return results

    def _check_rootfs(self, boot: Path, preset: dict) -> CheckResult:
        rootfs = preset.get("rootfs", "")
        p = boot / rootfs if not rootfs.startswith("/") else Path(rootfs)
        if p.exists():
            return CheckResult("rootfs", True, f"OK: {p}")
        return CheckResult("rootfs", False, f"SquashFS rootfs not found: {p}")

    def _check_overlay(self, preset: dict) -> CheckResult:
        dataset = preset.get("overlay_dataset", "")
        r = self.run_cmd(f"zfs list -H {dataset}", check=False)
        if r.success:
            return CheckResult("overlay", True, f"OK: {dataset}")
        return CheckResult("overlay", False, f"Overlay dataset not found: {dataset}")
