# Détection avancée — fsdeploy

**Document technique** — Scan approfondi, MD5, validation squashfs, identification partitions

---

## Vue d'ensemble

La détection fsdeploy combine **plusieurs stratégies** :

1. **Scan de structure** : arborescence de fichiers (glob patterns)
2. **Scan de contenu** : magic bytes, headers, signatures
3. **Identification partitions** : UUID, labels, filesystem types
4. **Déduplication kernels** : MD5 hash pour détecter doublons
5. **Validation squashfs** : test montage + scan contenu
6. **Scoring de confiance** : agrégation pondérée des signaux

---

## 1. Scan de structure (ROLE_PATTERNS)

### Patterns par rôle

```python
ROLE_PATTERNS = [
    {
        "role": "boot",
        "globs": [
            "vmlinuz-*",           # kernels
            "initrd.img-*",        # initramfs
            "config-*",            # kernel configs
            "System.map-*",        # symbol maps
            "grub/",               # GRUB (si présent)
            "efi/",                # EFI (si présent)
        ],
        "min": 2,                  # au moins 2 matches
        "prio": 10,                # priorité haute
    },
    {
        "role": "kernel",
        "globs": [
            "vmlinuz-*",
            "vmlinux-*",
            "*.efi",               # EFI bundles
        ],
        "min": 1,
        "prio": 9,
    },
    {
        "role": "initramfs",
        "globs": [
            "initrd.img-*",
            "initramfs-*.img",
            "initrd-*.img",
        ],
        "min": 1,
        "prio": 8,
    },
    {
        "role": "squashfs",
        "globs": [
            "*.sfs",
            "*.squashfs",
            "*.sqfs",
        ],
        "min": 1,
        "prio": 7,
    },
    {
        "role": "modules",
        "globs": [
            "lib/modules/*",
            "modules/*/kernel/",
        ],
        "min": 1,
        "prio": 6,
    },
    {
        "role": "rootfs",
        "globs": [
            "bin/bash",
            "etc/fstab",
            "usr/bin/",
            "var/log/",
        ],
        "min": 3,
        "prio": 5,
    },
    {
        "role": "overlay",
        "globs": [
            "upper/",
            "work/",
            "merged/",
        ],
        "min": 2,
        "prio": 4,
    },
    {
        "role": "python_env",
        "globs": [
            "bin/python*",
            "lib/python*/",
            "pyvenv.cfg",
        ],
        "min": 2,
        "prio": 3,
    },
    {
        "role": "efi",
        "globs": [
            "EFI/",
            "*.efi",
            "grubx64.efi",
        ],
        "min": 1,
        "prio": 2,
    },
]
```

### Algorithme de scoring

```python
def _score_patterns(self, path: Path) -> tuple[str, float, dict]:
    """
    Retourne : (role, confidence, details)
    
    Confidence : 0.0 (aucun match) → 1.0 (tous les globs matchent)
    """
    best = {"role": "data", "score": 0.0, "details": {}, "prio": -1}
    
    for pattern in ROLE_PATTERNS:
        matches = []
        for glob_pattern in pattern["globs"]:
            found = list(path.glob(glob_pattern))[:20]  # limite 20 pour perf
            if found:
                matches.append({
                    "pattern": glob_pattern,
                    "count": len(found),
                    "samples": [str(f.relative_to(path)) for f in found[:3]],
                })
        
        # Score brut : ratio matches / total globs
        score_raw = len(matches) / max(len(pattern["globs"]), 1)
        
        # Seuil minimal : au moins pattern["min"] globs doivent matcher
        if len(matches) < pattern["min"]:
            continue
        
        # Priorité : en cas d'égalité de score, prendre le rôle prioritaire
        if (pattern["prio"] > best["prio"] or
                (pattern["prio"] == best["prio"] and score_raw > best["score"])):
            best = {
                "role": pattern["role"],
                "score": score_raw,
                "details": {"matches": matches, "pattern_name": pattern["role"]},
                "prio": pattern["prio"],
            }
    
    return best["role"], best["score"], best["details"]
```

---

## 2. Scan de contenu (magic bytes)

### Détection par signatures

```python
MAGIC_SIGNATURES = {
    "squashfs": {
        "offset": 0,
        "bytes": b"hsqs",  # SquashFS magic (little-endian)
        "role": "squashfs",
    },
    "squashfs_be": {
        "offset": 0,
        "bytes": b"sqsh",  # SquashFS magic (big-endian)
        "role": "squashfs",
    },
    "ext4": {
        "offset": 0x438,
        "bytes": b"\x53\xEF",  # EXT4 magic
        "role": "rootfs",
    },
    "gzip": {
        "offset": 0,
        "bytes": b"\x1f\x8b",  # gzip header
        "role": "initramfs",  # probablement un initramfs compressé
    },
    "cpio": {
        "offset": 0,
        "bytes": b"070707",  # cpio ASCII header
        "role": "initramfs",
    },
    "elf": {
        "offset": 0,
        "bytes": b"\x7fELF",  # ELF header
        "role": "kernel",  # probablement un kernel
    },
}

def _scan_magic_bytes(self, file_path: Path) -> str | None:
    """Détecte le type de fichier par magic bytes."""
    try:
        with file_path.open("rb") as f:
            # Lire les premiers 4K (suffisant pour la plupart des headers)
            header = f.read(4096)
            
            for sig_name, sig in MAGIC_SIGNATURES.items():
                offset = sig["offset"]
                magic = sig["bytes"]
                
                if offset + len(magic) <= len(header):
                    if header[offset:offset + len(magic)] == magic:
                        return sig["role"]
        
        return None
    except (OSError, PermissionError):
        return None
```

### Détection kernels

```python
def _is_kernel_file(self, file_path: Path) -> bool:
    """Détecte si un fichier est un kernel Linux."""
    # 1. Nom du fichier
    name = file_path.name.lower()
    if not any(name.startswith(prefix) for prefix in ["vmlinuz", "vmlinux", "bzimage"]):
        return False
    
    # 2. Taille (kernels Linux : 5-15 MB typiquement)
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb < 3 or size_mb > 50:
        return False
    
    # 3. Magic bytes (ELF ou bzImage header)
    try:
        with file_path.open("rb") as f:
            header = f.read(1024)
            
            # ELF kernel
            if header[:4] == b"\x7fELF":
                return True
            
            # bzImage kernel (offset 0x202: "HdrS")
            if len(header) > 0x202 + 4:
                if header[0x202:0x206] == b"HdrS":
                    return True
        
        return False
    except OSError:
        return False
```

---

## 3. Identification des partitions

### Par UUID et label

```python
def _detect_partitions(self) -> list[dict]:
    """Détecte les partitions via blkid et lsblk."""
    partitions = []
    
    # lsblk pour liste complète
    r = self.run_cmd(
        "lsblk -ln -o NAME,FSTYPE,LABEL,UUID,SIZE,TYPE,MOUNTPOINT",
        check=False
    )
    
    for line in r.stdout.strip().splitlines():
        parts = line.split(None, 6)
        if len(parts) < 6 or parts[5] != "part":
            continue
        
        device = f"/dev/{parts[0]}"
        fstype = parts[1] if parts[1] != "" else "-"
        label = parts[2] if parts[2] != "" else "-"
        uuid = parts[3] if parts[3] != "" else "-"
        size = parts[4]
        mountpoint = parts[6] if len(parts) > 6 else "-"
        
        # Détection du rôle par type et label
        role = self._identify_partition_role(fstype, label, device)
        
        partitions.append({
            "device": device,
            "fstype": fstype,
            "label": label,
            "uuid": uuid,
            "size": size,
            "mountpoint": mountpoint,
            "role": role,
        })
    
    return partitions

def _identify_partition_role(self, fstype: str, label: str, device: str) -> str:
    """Identifie le rôle d'une partition."""
    # EFI
    if fstype in ("vfat", "fat32", "fat16"):
        return "efi"
    
    # Swap
    if fstype == "swap":
        return "swap"
    
    # Label contient "boot"
    if label and "boot" in label.lower():
        return "boot"
    
    # Label contient "efi"
    if label and "efi" in label.lower():
        return "efi"
    
    # ZFS
    if "zfs" in fstype.lower():
        return "zfs"
    
    # Ext4/XFS/Btrfs
    if fstype in ("ext4", "xfs", "btrfs"):
        return "rootfs"
    
    return "data"
```

### Scan du contenu des partitions

```python
def _probe_partition_content(self, device: str, fstype: str) -> dict:
    """Monte temporairement une partition et scanne son contenu."""
    if fstype in ("swap", "zfs_member", "-"):
        return {"role": "unknown", "confidence": 0.0}
    
    # Montage temporaire
    temp_mount = tempfile.mkdtemp(prefix="fsdeploy-part-")
    
    try:
        # Essayer mount
        r = self.run_cmd(f"mount -o ro {device} {temp_mount}", sudo=True, check=False)
        if not r.success:
            return {"role": "unknown", "confidence": 0.0}
        
        # Scan de structure
        role, confidence, details = self._score_patterns(Path(temp_mount))
        
        # Démontage
        self.run_cmd(f"umount {temp_mount}", sudo=True, check=False)
        
        return {"role": role, "confidence": confidence, "details": details}
    
    finally:
        try:
            os.rmdir(temp_mount)
        except OSError:
            pass
```

---

## 4. Déduplication kernels (MD5)

### Détection de kernels dupliqués

```python
import hashlib

def _scan_kernels_with_dedup(self, path: Path) -> list[dict]:
    """
    Scanne les kernels et détecte les doublons par MD5.
    
    Retourne : [
        {
            "path": "/mnt/boot/vmlinuz-6.12.0",
            "version": "6.12.0",
            "md5": "a1b2c3...",
            "size": 15728640,
            "is_duplicate": False,
            "duplicate_of": None,
        },
        {
            "path": "/mnt/boot/vmlinuz-6.12.0-copy",
            "version": "6.12.0",
            "md5": "a1b2c3...",  # même MD5
            "size": 15728640,
            "is_duplicate": True,
            "duplicate_of": "/mnt/boot/vmlinuz-6.12.0",
        },
    ]
    """
    kernels = []
    md5_map = {}  # md5 → first kernel path
    
    # 1. Trouver tous les fichiers kernel
    kernel_files = list(path.glob("vmlinuz-*")) + list(path.glob("vmlinux-*"))
    
    for kernel_file in kernel_files:
        if not self._is_kernel_file(kernel_file):
            continue
        
        # 2. Calculer MD5
        md5_hash = self._compute_md5(kernel_file)
        
        # 3. Extraire version
        version = self._extract_kernel_version(kernel_file.name)
        
        # 4. Vérifier si doublon
        is_duplicate = False
        duplicate_of = None
        
        if md5_hash in md5_map:
            is_duplicate = True
            duplicate_of = md5_map[md5_hash]
        else:
            md5_map[md5_hash] = str(kernel_file)
        
        kernels.append({
            "path": str(kernel_file),
            "version": version,
            "md5": md5_hash,
            "size": kernel_file.stat().st_size,
            "is_duplicate": is_duplicate,
            "duplicate_of": duplicate_of,
        })
    
    # 5. Tri par version (plus récent d'abord)
    kernels.sort(key=lambda k: k["version"], reverse=True)
    
    return kernels

def _compute_md5(self, file_path: Path, chunk_size: int = 8192) -> str:
    """Calcule le MD5 d'un fichier."""
    md5 = hashlib.md5()
    
    with file_path.open("rb") as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    
    return md5.hexdigest()

def _extract_kernel_version(self, filename: str) -> str:
    """Extrait la version d'un nom de kernel."""
    # vmlinuz-6.12.0-amd64 → 6.12.0
    # vmlinux-5.10.0-21-generic → 5.10.0
    
    import re
    
    # Pattern : vmlinuz-VERSION ou vmlinux-VERSION
    match = re.search(r'(?:vmlinuz|vmlinux)-([0-9]+\.[0-9]+\.[0-9]+)', filename)
    if match:
        return match.group(1)
    
    return "unknown"
```

### Affichage dans la TUI

```python
# Dans KernelScreen :
def _refresh_kernel_list(self):
    """Affiche les kernels avec indication des doublons."""
    dt = self.query_one("#kernel-table", DataTable)
    dt.clear()
    
    for kernel in self._kernels:
        version = kernel["version"]
        size_mb = f"{kernel['size'] / (1024**2):.1f} MB"
        md5_short = kernel["md5"][:8]
        
        if kernel["is_duplicate"]:
            status = f"❌ DOUBLON de {Path(kernel['duplicate_of']).name}"
        else:
            status = "✅ OK"
        
        dt.add_row(version, kernel["path"], size_mb, md5_short, status)
```

---

## 5. Validation squashfs

### Test de montage + scan

```python
def _validate_squashfs(self, sfs_path: Path) -> dict:
    """
    Valide un fichier squashfs :
    1. Vérification magic bytes
    2. Test montage
    3. Scan contenu
    4. Détection du type (rootfs, modules, python_env)
    
    Retourne : {
        "valid": True/False,
        "mountable": True/False,
        "content_type": "rootfs" | "modules" | "python_env" | "unknown",
        "confidence": 0.0-1.0,
        "details": {...}
    }
    """
    result = {
        "valid": False,
        "mountable": False,
        "content_type": "unknown",
        "confidence": 0.0,
        "details": {},
    }
    
    # 1. Vérifier magic bytes
    if not self._check_squashfs_magic(sfs_path):
        result["details"]["error"] = "invalid magic bytes"
        return result
    
    result["valid"] = True
    
    # 2. Test montage
    temp_mount = tempfile.mkdtemp(prefix="fsdeploy-sqfs-")
    
    try:
        r = self.run_cmd(
            f"mount -t squashfs -o loop,ro {sfs_path} {temp_mount}",
            sudo=True,
            check=False
        )
        
        if not r.success:
            result["details"]["error"] = f"mount failed: {r.stderr}"
            return result
        
        result["mountable"] = True
        
        # 3. Scan contenu
        content_type, confidence, details = self._analyze_squashfs_content(
            Path(temp_mount)
        )
        
        result["content_type"] = content_type
        result["confidence"] = confidence
        result["details"]["content"] = details
        
        # Démontage
        self.run_cmd(f"umount {temp_mount}", sudo=True, check=False)
        
    finally:
        try:
            os.rmdir(temp_mount)
        except OSError:
            pass
    
    return result

def _check_squashfs_magic(self, sfs_path: Path) -> bool:
    """Vérifie le magic header squashfs."""
    try:
        with sfs_path.open("rb") as f:
            magic = f.read(4)
            # hsqs (little-endian) ou sqsh (big-endian)
            return magic in (b"hsqs", b"sqsh")
    except OSError:
        return False

def _analyze_squashfs_content(self, mount_path: Path) -> tuple[str, float, dict]:
    """Analyse le contenu d'un squashfs monté."""
    # Patterns spécifiques aux squashfs
    SFS_PATTERNS = {
        "rootfs": {
            "globs": ["bin/bash", "etc/fstab", "usr/bin/", "lib/"],
            "min": 3,
        },
        "modules": {
            "globs": ["lib/modules/*/kernel/", "lib/modules/*/modules.dep"],
            "min": 1,
        },
        "python_env": {
            "globs": ["bin/python*", "lib/python*/", "pyvenv.cfg"],
            "min": 2,
        },
    }
    
    for content_type, pattern in SFS_PATTERNS.items():
        matches = []
        for glob in pattern["globs"]:
            if list(mount_path.glob(glob)):
                matches.append(glob)
        
        if len(matches) >= pattern["min"]:
            confidence = len(matches) / len(pattern["globs"])
            return content_type, confidence, {"matches": matches}
    
    return "unknown", 0.0, {}
```

---

## 6. Scoring de confiance agrégé

### Combinaison des signaux

```python
def _compute_aggregate_confidence(self, signals: dict) -> float:
    """
    Agrège plusieurs signaux de détection.
    
    signals = {
        "pattern_match": 0.85,    # score patterns
        "magic_bytes": 1.0,       # magic bytes détecté (1.0) ou non (0.0)
        "content_scan": 0.90,     # scan approfondi
        "partition_type": 0.75,   # type partition (pour partitions)
    }
    
    Retourne : confiance agrégée (0.0-1.0)
    """
    weights = {
        "pattern_match": 0.4,
        "magic_bytes": 0.3,
        "content_scan": 0.2,
        "partition_type": 0.1,
    }
    
    total_weight = 0.0
    weighted_sum = 0.0
    
    for signal_name, confidence in signals.items():
        weight = weights.get(signal_name, 0.0)
        if weight > 0:
            weighted_sum += confidence * weight
            total_weight += weight
    
    if total_weight == 0:
        return 0.0
    
    return weighted_sum / total_weight
```

### Exemple d'utilisation

```python
@security.detect.dataset
class EnhancedDatasetProbeTask(Task):
    """Probe avancé avec multiple signaux."""
    
    def run(self) -> dict:
        dataset = self.params["dataset"]
        
        # Montage temporaire
        temp_mount = self._mount_temp(dataset)
        
        try:
            signals = {}
            
            # Signal 1 : Pattern matching
            role_pattern, conf_pattern, _ = self._score_patterns(temp_mount)
            signals["pattern_match"] = conf_pattern
            
            # Signal 2 : Magic bytes sur fichiers clés
            magic_detected = self._scan_magic_bytes_dir(temp_mount)
            signals["magic_bytes"] = 1.0 if magic_detected else 0.0
            
            # Signal 3 : Content scan approfondi
            conf_content = self._deep_content_scan(temp_mount)
            signals["content_scan"] = conf_content
            
            # Agrégation
            final_confidence = self._compute_aggregate_confidence(signals)
            
            return {
                "dataset": dataset,
                "role": role_pattern,
                "confidence": final_confidence,
                "signals": signals,
            }
        
        finally:
            self._umount_temp(temp_mount)
```

---

## 7. Workflow complet de détection

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Import pools (no-mount)                                  │
│    zpool import -f -N boot_pool                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Liste datasets                                           │
│    zfs list -r boot_pool                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Pour chaque dataset : Probe                              │
│    ┌─────────────────────────────────────────────────────┐ │
│    │ a. Montage temporaire                                │ │
│    │    mount -t zfs dataset /tmp/probe-xyz              │ │
│    ├─────────────────────────────────────────────────────┤ │
│    │ b. Scan structure (glob patterns)                   │ │
│    │    path.glob("vmlinuz-*")                           │ │
│    │    → role: boot, confidence: 0.85                   │ │
│    ├─────────────────────────────────────────────────────┤ │
│    │ c. Scan contenu (magic bytes)                       │ │
│    │    f.read(4) == b"hsqs" → squashfs                  │ │
│    │    → confidence: 1.0                                │ │
│    ├─────────────────────────────────────────────────────┤ │
│    │ d. Scan approfondi                                  │ │
│    │    - Kernels: MD5 dedup                             │ │
│    │    - Squashfs: test mount + analyze                 │ │
│    │    → confidence: 0.90                               │ │
│    ├─────────────────────────────────────────────────────┤ │
│    │ e. Agrégation scores                                │ │
│    │    0.4×0.85 + 0.3×1.0 + 0.2×0.90 = 0.86            │ │
│    ├─────────────────────────────────────────────────────┤ │
│    │ f. Démontage                                        │ │
│    │    umount /tmp/probe-xyz                            │ │
│    └─────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Résultat agrégé                                          │
│    {                                                         │
│      "boot_pool/boot": {                                    │
│        "role": "boot",                                      │
│        "confidence": 0.86,                                  │
│        "signals": {                                         │
│          "pattern_match": 0.85,                            │
│          "magic_bytes": 1.0,                               │
│          "content_scan": 0.90                              │
│        },                                                   │
│        "kernels": [                                         │
│          {"version": "6.12.0", "md5": "a1b2...", "dup": false}, │
│          {"version": "6.6.47", "md5": "c3d4...", "dup": false}  │
│        ]                                                    │
│      }                                                      │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Affichage dans la TUI

### DetectionScreen avec détails

```
┌───────────────────────────────────────────────────────────────┐
│  Détection des datasets                                       │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dataset             │ Rôle      │ Conf.  │ Signaux            │
│ ────────────────────────────────────────────────────────────── │
│  boot_pool/boot      │ boot      │ 86%    │ ✅✅✅             │
│  boot_pool/images    │ squashfs  │ 95%    │ ✅✅✅ (monté OK)  │
│  fast_pool/overlay   │ overlay   │ 75%    │ ✅✅              │
│                                                                 │
│  [Détails sélectionné : boot_pool/boot]                       │
│    Signaux :                                                   │
│      - Pattern match : 85% (vmlinuz-*, initrd.img-*, config-*) │
│      - Magic bytes   : 100% (ELF kernel détecté)              │
│      - Content scan  : 90% (structure boot valide)            │
│                                                                 │
│    Kernels détectés :                                          │
│      - vmlinuz-6.12.0    (MD5: a1b2c3..., 15.2 MB) ✅         │
│      - vmlinuz-6.6.47    (MD5: c3d4e5..., 14.8 MB) ✅         │
│      - vmlinuz-6.12.0.bak (MD5: a1b2c3..., 15.2 MB) ❌ DOUBLON│
│                                                                 │
│    Squashfs trouvés :                                          │
│      - rootfs.sfs (200 MB) ✅ Valide (rootfs, conf: 95%)      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Actions :
  [r] Rafraîchir   [Enter] Suivant (Montages)   [Esc] Retour
```

---

## Conclusion

### Avantages de la détection avancée

1. **Robustesse** : multiple signaux → confiance élevée
2. **Déduplication** : économie d'espace (kernels dupliqués détectés)
3. **Validation** : squashfs testés avant utilisation
4. **Précision** : scoring agrégé réduit faux positifs
5. **Transparence** : utilisateur voit les signaux dans la TUI

### Prochaines étapes

- Intégration dans le code existant (`lib/function/detect/`)
- Tests avec topologies ZFS variées
- Optimisation performance (cache MD5, scan parallèle)
- Extension patterns pour autres distributions

---

**Document technique fsdeploy**  
**Version** : 1.0  
**Date** : 21 mars 2026
