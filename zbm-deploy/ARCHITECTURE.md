# ZFSBootMenu Custom — Architecture complète

## Matériel cible

| Composant | Détail |
|-----------|--------|
| CPU | i5-11400 |
| Carte mère | Z490 UD |
| RAM | 128 GB DDR4 |
| NVMe-A (M.2_1) | boot_pool — partition EFI + dataset ZFS /boot |
| NVMe-B (M.2_2) | fast_pool — entier, datasets overlay/var/log/tmp |
| 5× SATA 4 TB | data_pool — RAIDZ2, home + archives |

---

## Pools ZFS

```
boot_pool     /boot          NVMe-A partition ZFS
fast_pool     (datasets)     NVMe-B entier
data_pool     (datasets)     SATA RAIDZ2
```

### Datasets par système

Architecture **overlay** : chaque système n'a qu'**un seul dataset ZFS** de persistance.

```
fast_pool/overlay-<s>    mountpoint=none   upper OverlayFS (rw, canmount=noauto)

data_pool/home           /home             utilisateurs (partagé entre systèmes)
data_pool/archives/<s>   none              snapshots cold storage (optionnel)
```

**Pourquoi un seul dataset ?**
Le rootfs est un squashfs (`.sfs`) monté en **lower** (ro). Il contient déjà `/var`, `/tmp`, `/etc`, `/home`. Toutes les écritures vont dans l'**upper** (`fast_pool/overlay-<s>/upper`). Pas de datasets `var-`, `log-`, `tmp-` séparés.

**Le failsafe suit la même règle :**
```
fast_pool/overlay-failsafe    mountpoint=none   upper OverlayFS failsafe
(pas de home pour failsafe)
```

---

## Convention de nommage des images (`naming.sh`)

### Règle fondamentale

**`kernel`, `initramfs`, `modules` sont INDÉPENDANTS des rootfs.**
Le rootfs ne contient jamais de kernel ni de modules.

```
/boot/images/
  kernels/      kernel-<label>-<YYYYMMDD>
  initramfs/    initramfs-<type>-<YYYYMMDD>.img
  modules/      modules-<label>-<YYYYMMDD>.sfs
  rootfs/       rootfs-<system>-<label>-<YYYYMMDD>.sfs   ← seul avec system
  startup/      python-<ver>-<YYYYMMDD>.sfs
  failsafe/     kernel-failsafe-<label>-<YYYYMMDD>
                initramfs-failsafe-<type>-<YYYYMMDD>.img
                modules-failsafe-<label>-<YYYYMMDD>.sfs
                rootfs-failsafe-<label>-<YYYYMMDD>.sfs
```

### Types d'initramfs (= label de l'initramfs)

| Label | Init | Description |
|-------|------|-------------|
| `zbm` | Notre init | OverlayFS + /var/tmp ZFS + Python TUI + stream |
| `zbm-stream` | Variante stream | Même overlay, sans TUI Python |
| `minimal` | Init natif noyau | Boot direct rootfs, pas d'overlay |
| `custom-<n>` | Personnalisé | Script custom |

### Exemples

```
kernel-generic-6.12-20250310
kernel-custom-i5-11400-6.12-20250310
initramfs-zbm-20250310.img
initramfs-zbm-stream-20250310.img
initramfs-minimal-20250310.img
modules-generic-6.12-20250310.sfs
rootfs-systeme1-gentoo-20250310.sfs
rootfs-systeme2-arch-20250310.sfs
python-3.11-20250310.sfs
```

---

## Séquence de montage au boot (`initramfs-init`)

### Deux modes

#### Mode SYSTÈME (zbm_rootfs défini)

```
boot_pool                  → /mnt/boot         (ZFS, ro)
modules-<label>.sfs        → /mnt/modloop      (squashfs, ro)
python-<ver>.sfs           → /mnt/python       (squashfs, ro)
rootfs-<s>-<label>.sfs     → /mnt/lower        (squashfs, lower layer ro)
fast_pool/overlay-<s>      → /mnt/fast         (ZFS, rw)
  upper = /mnt/fast/upper
  work  = /mnt/fast/.work
OverlayFS                  → /mnt/merged       (lower+upper)
# /var /tmp → écrits dans upper (fast_pool/overlay-<s>/upper) — pas de datasets séparés
data_pool/home             → /mnt/merged/home
bind: /mnt/boot            → /mnt/merged/mnt/boot
bind: /mnt/python          → /mnt/merged/mnt/python
bind: /mnt/modloop/lib/modules/<kver> → /mnt/merged/lib/modules/<kver>
pivot_root /mnt/merged
exec /sbin/init
```

Points clés :
- Chaque système a son propre upper `fast_pool/overlay-<s>` — aucun partage
- `/var`, `/tmp` sont dans le **lower (squashfs)** et redirigés vers l'**upper** par overlayfs — aucun dataset ZFS séparé
- Le rootfs squashfs est **toujours read-only** — les écritures vont dans l'upper overlay

#### Mode INIT-ONLY (zbm_rootfs absent ou "none")

Pas de squashfs, pas d'overlay, pas de pivot_root.
On reste dans l'environnement initramfs.

```
boot_pool                  → /mnt/boot         (ZFS)
modules-<label>.sfs        → /mnt/modloop      (optionnel)
python-<ver>.sfs           → /mnt/python       (optionnel)
→ exec zbm_exec            (ou auto : Python TUI → shell)
```

Utile pour : premier boot, rescue, configuration initiale, scripts de setup.

### Cmdline kernel

**Mode système :**
```
zbm_system=systeme1
zbm_rootfs=/boot/images/rootfs/rootfs-systeme1-gentoo-20250310.sfs
zbm_modules=/boot/images/modules/modules-generic-6.12-20250310.sfs
zbm_overlay=fast_pool/overlay-systeme1
```

**Mode init-only :**
```
zbm_system=initial
zbm_rootfs=none
zbm_exec=/mnt/python/launch.sh      (optionnel — auto si absent)
```

---

## Types de presets de boot (`presets.sh`)

| Type | Init | Rootfs | Description |
|------|------|--------|-------------|
| `initial` | zbm | null | Premier boot, init-only, Python TUI |
| `prepared` | zbm | ✓ | Boot complet : overlay + var/tmp + Python TUI + stream |
| `normal` | zbm | ✓ | Boot système standard, sans TUI Python |
| `stream` | zbm-stream | ✓ | Boot flux vidéo, sans TUI Python |
| `minimal` | minimal | ✓ ou null | Init natif noyau |
| `failsafe` | zbm | ✓ | Protégé, non modifiable par l'UI |

### Preset initial (premier boot)

```json
{
  "name":       "initial",
  "type":       "prepared",
  "_boot_mode": "init-only",
  "rootfs":     null,
  "cmdline":    "quiet loglevel=3 zbm_system=initial zbm_rootfs=none"
}
```

---

## Fichiers du projet

### Déploiement (`deploy/`)

| Fichier | Rôle |
|---------|------|
| `deploy.sh` | Orchestrateur principal — menu interactif |
| `lib/naming.sh` | Convention de nommage — fonctions zbm_stem/zbm_parse/zbm_path… |
| `lib/coherence.sh` | Audit cohérence : nommage + presets + datasets ZFS |
| `lib/import-mount.sh` | Import pools ZFS + montage datasets (deploy-time) |
| `lib/umount.sh` | Démontage propre |
| `lib/detect.sh` | Détection hardware : NVMe, SATA, pools |
| `lib/datasets-check.sh` | Vérification + création datasets ZFS |
| `lib/kernel.sh` | Installation kernel + modules squashfs (indépendant rootfs) |
| `lib/rootfs.sh` | Copie + enregistrement d'un rootfs squashfs |
| `lib/python-sfs.sh` | Construction python-<ver>.sfs |
| `lib/initramfs.sh` | Construction initramfs (zbm / zbm-stream / minimal / custom) |
| `lib/zbm.sh` | Installation ZFSBootMenu EFI |
| `lib/presets.sh` | Génération presets JSON (--initial / --full) |
| `lib/failsafe.sh` | Vérification failsafe |

### Init / boot

| Fichier | Rôle |
|---------|------|
| `initramfs-init` | Init principal : overlay + pivot ou init-only |
| `initramfs-stream-init` | Variante stream : même overlay, sans TUI Python |

### Runtime

| Fichier | Rôle |
|---------|------|
| `system/zbm-startup` | Service OpenRC/systemd : démarrage stream, réseau, TUI |
| `python-interface.py` | Interface TUI Python (Textual) : presets, snapshots, hotswap, stream |

### Failsafe

| Fichier | Rôle |
|---------|------|
| `create-failsafe.sh` | Création failsafe depuis un système existant |
| `update-failsafe-links.sh` | Mise à jour failsafe |
| `cron-tasks.sh` | Tâches planifiées : snapshots automatiques |

---

## Workflow de déploiement

```
bash deploy/deploy.sh
  → 0. import-mount      : importer les pools ZFS
  → 1. detect            : détecter le matériel
  → 2. datasets          : créer datasets ZFS (--initial pour premier boot)
  → 3a. rootfs           : copier un rootfs squashfs
  → 3b. kernel           : installer kernel + modules (indépendant)
  → 4. python-sfs        : construire python-*.sfs
  → 5. initramfs         : construire initramfs-zbm-*.img
  → 6. zbm               : installer ZFSBootMenu EFI
  → 7. presets           : générer presets JSON
  → 8. failsafe          : créer le preset failsafe protégé
```

### Premier boot

1. `presets.sh --initial` génère `presets/initial.json` (init-only, rootfs=null)
2. ZFSBootMenu démarre, sélectionne le preset initial
3. `initramfs-init` entre en mode init-only : monte boot_pool + python.sfs
4. Python TUI démarre depuis `/mnt/python/launch.sh`
5. Depuis la TUI : configurer un rootfs, créer les datasets système, générer les presets

---

## Interface Python (`python-interface.py`)

### Écrans principaux

| Écran | Accès | Fonction |
|-------|-------|----------|
| `MainScreen` | démarrage | Liste presets, symlinks actifs, état stream |
| `PresetConfigScreen` | `[C]` | Créer/modifier preset — 4 selects indépendants : kernel / initramfs / modules / rootfs |
| `HotSwapScreen` | `[H]` | kexec live : changer kernel/initramfs/modules/rootfs sans reboot |
| `StreamScreen` | `[S]` | Contrôle stream YouTube (start/stop/countdown) |
| `SnapshotScreen` | `[Z]` | Snapshots ZFS par profil |
| `CoherenceScreen` | `[K]` | Audit cohérence complète |
| `FailsafeScreen` | `[F]` | Infos failsafe (lecture seule) |

### Règles UI

- Le failsafe (`protected: true`) n'est **jamais modifiable** depuis l'UI
- Le preset initial (rootfs=null) est affiché avec `🔧 Mode INIT-ONLY`
- Les datasets sont auto-remplis quand un rootfs est sélectionné (`on_rootfs_changed`)
- La cmdline est regénérée à chaque sauvegarde de preset

---

## Invariants du système

1. **Kernel / initramfs / modules** n'ont pas de champ `system` dans leur nom
2. **Le rootfs squashfs** ne contient jamais de kernel ni de modules
3. **Chaque système** a son propre upper overlay `fast_pool/overlay-<s>` — isolation complète
4. **`/var`, `/var/log`, `/tmp`** sont montés par l'initramfs avant `pivot_root`, pas par OpenRC
5. **Le failsafe** est géré uniquement par `create-failsafe.sh` et `update-failsafe-links.sh`
6. **Un preset peut avoir rootfs=null** — c'est le mode init-only, valide et géré
