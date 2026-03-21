# Graphiques et Diagrammes — fsdeploy

**Documentation visuelle** — Schémas descriptifs du fonctionnement

---

## 1. Architecture globale — Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEBIAN LIVE TRIXIE                                 │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ launch.sh (bootstrap)                                                 │  │
│  │                                                                        │  │
│  │  1. APT sources (contrib, non-free, backports)                       │  │
│  │     ├─> zfsutils-linux, zfs-dkms                                     │  │
│  │     ├─> dracut, squashfs-tools, ffmpeg                               │  │
│  │     └─> linux-headers-amd64                                          │  │
│  │                                                                        │  │
│  │  2. DKMS compilation ZFS (polling loop max 180s)                     │  │
│  │                                                                        │  │
│  │  3. Groupe fsdeploy + sudoers granulaire                             │  │
│  │     ├─> chmod 2775 /opt/fsdeploy (setgid + POSIX ACL)               │  │
│  │     └─> visudo -cf validation                                        │  │
│  │                                                                        │  │
│  │  4. Git clone + venv + pip install                                   │  │
│  │     └─> github.com/newicody/fsdeploy                                 │  │
│  └────────────────────────┬─────────────────────────────────────────────┘  │
│                            │                                                 │
│                            ▼                                                 │
│                   python3 -m fsdeploy                                        │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FSDEPLOY DAEMON (processus racine)                    │
│                                                                               │
│  ┌────────────────┐      ┌─────────────────┐      ┌──────────────────┐    │
│  │   Config       │      │   Log           │      │   Runtime        │    │
│  │   ──────       │      │   ───           │      │   ───────        │    │
│  │ fsdeploy.conf  │──┐   │ structlog       │──┐   │ RuntimeState     │    │
│  │ (19 sections)  │  │   │ + ASCII fallback│  │   │ (thread-safe)    │    │
│  │ configobj      │  │   │ HuffmanStore    │  │   │ Lock mutations   │    │
│  └────────────────┘  │   └─────────────────┘  │   └──────────────────┘    │
│                      │                        │                             │
│                      ▼                        ▼                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         SCHEDULER                                    │  │
│  │                                                                       │  │
│  │  Event Queue (PriorityQueue)                                        │  │
│  │     ├─> Priority.CRITICAL (coherence, sécurité)                     │  │
│  │     ├─> Priority.HIGH (montage, import)                             │  │
│  │     ├─> Priority.NORMAL (détection, snapshots)                      │  │
│  │     └─> Priority.LOW (maintenance, stats)                           │  │
│  │                                                                       │  │
│  │  Intent Queue (FIFO + handlers)                                     │  │
│  │     Event("mount.request") ──> MountRequestIntent                   │  │
│  │                                                                       │  │
│  │  Task Graph (DAG + cycle detection)                                 │  │
│  │     DatasetProbeTask → DatasetMountTask → MountVerifyTask           │  │
│  │                                                                       │  │
│  │  ThreadPoolExecutor (max_workers=4, tasks threaded)                 │  │
│  │     Thread 1: DatasetProbeTask (pool: boot_pool)                    │  │
│  │     Thread 2: SnapshotCreateTask (dataset: tank/home)               │  │
│  │     Thread 3: SquashfsValidateTask (file: rootfs.sfs)               │  │
│  │     Thread 4: (disponible)                                          │  │
│  │                                                                       │  │
│  └───────────────────────────┬─────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      BUS SOURCES                                     │  │
│  │                                                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │ TimerSource  │  │InotifySource │  │ UdevSource   │              │  │
│  │  │ ────────────│  │──────────────│  │ ────────────│              │  │
│  │  │ Coherence    │  │ /boot watch  │  │ Ajout/retrait│              │  │
│  │  │ Scrub        │  │ Nouveau      │  │ disques      │              │  │
│  │  │ Snapshots    │  │ kernel       │  │ Hotplug      │              │  │
│  │  │ auto         │  │ → refresh UI │  │ → detection  │              │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │  │
│  │         │                 │                 │                        │  │
│  │         └─────────────────┴─────────────────┘                        │  │
│  │                           │                                           │  │
│  │                           ▼                                           │  │
│  │                    Event → Scheduler                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    TUI TEXTUAL (enfant optionnel)                    │  │
│  │                                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Bridge (thread-safe)                                         │  │  │
│  │  │  ──────                                                        │  │  │
│  │  │  emit("mount.request") ───> EventQueue                        │  │  │
│  │  │  poll() ◄───────────────── RuntimeState.completed             │  │  │
│  │  │  Tickets (UUID) pour traçabilité                              │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  Écrans (11) :                                                       │  │
│  │    h: WelcomeScreen     → Mode deploy/gestion                       │  │
│  │    d: DetectionScreen   → Pools/datasets/partitions + confiance     │  │
│  │    m: MountsScreen      → Validation/modification montages          │  │
│  │    k: KernelScreen      → Sélection/compilation kernel              │  │
│  │    i: InitramfsScreen   → Type zbm/minimal/stream                   │  │
│  │    p: PresetsScreen     → CRUD presets JSON                         │  │
│  │    c: CoherenceScreen   → Vérification complète système             │  │
│  │    s: SnapshotsScreen   → Gestion snapshots                         │  │
│  │    y: StreamScreen      → Config YouTube                            │  │
│  │    o: ConfigScreen      → Éditeur fsdeploy.conf                     │  │
│  │    x: DebugScreen       → Logs/tasks/state                          │  │
│  │                                                                       │  │
│  │  Mode web : textual-web sur port 8080                               │  │
│  │  Restart auto si crash (backoff exponentiel)                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pipeline Event → Intent → Task

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE DE TRAITEMENT                         │
└─────────────────────────────────────────────────────────────────────────┘

     SOURCES                SCHEDULER              EXECUTION
         │                      │                      │
         ▼                      ▼                      ▼

┌──────────────┐       ┌─────────────┐       ┌────────────────┐
│  TUI Bridge  │       │ EventQueue  │       │ ThreadPool     │
│  emit()      │──────>│ (Priority)  │       │ Executor       │
└──────────────┘       └──────┬──────┘       └────────────────┘
                              │
┌──────────────┐              │
│ TimerSource  │──────────────┤
└──────────────┘              │
                              │
┌──────────────┐              │
│InotifySource │──────────────┤
└──────────────┘              │
                              │
┌──────────────┐              │
│ UdevSource   │──────────────┤
└──────────────┘              │
                              │
┌──────────────┐              │
│SocketSource  │──────────────┘
└──────────────┘              
                              
         │                    │
         ▼                    ▼
     
    EVENT                INTENT HANDLER           TASK BUILDER
    ─────                ──────────────           ────────────

┌──────────────┐       ┌──────────────┐       ┌────────────────┐
│ Event        │       │ @register    │       │ Intent         │
│              │       │ _intent()    │       │ .build_tasks() │
│ name         │──────>│              │──────>│                │
│ params       │       │ Handler      │       │ [Task1,        │
│ priority     │       │ mapping      │       │  Task2, ...]   │
│ context      │       │              │       │                │
└──────────────┘       └──────────────┘       └────────┬───────┘
                                                        │
    Exemple:                                            ▼
    
    Event(                                    ┌────────────────────┐
      name="mount.request",                   │ Security Resolver  │
      params={                                │ ────────────────── │
        "dataset": "boot_pool/boot",          │ @security.dataset  │
        "mountpoint": "/mnt/boot"             │ .mount             │
      }                                       │                    │
    )                                         │ Vérifie:           │
                                              │ - Permissions      │
                                              │ - Policies config  │
                                              │ - Locks requis     │
                                              └────────┬───────────┘
                                                       │
                                                       ▼
                                              ┌────────────────────┐
                                              │ TASK               │
                                              │ ────               │
                                              │ DatasetMountTask   │
                                              │                    │
                                              │ required_locks()   │
                                              │ required_resources()│
                                              │ validate()         │
                                              │ run()              │
                                              └────────┬───────────┘
                                                       │
                                                       ▼
                                              ┌────────────────────┐
                                              │ EXECUTION          │
                                              │ ─────────          │
                                              │ Thread 1           │
                                              │                    │
                                              │ sudo mount -t zfs  │
                                              │ boot_pool/boot     │
                                              │ /mnt/boot          │
                                              │                    │
                                              │ return {           │
                                              │   "mounted": True  │
                                              │ }                  │
                                              └────────┬───────────┘
                                                       │
                                                       ▼
                                              ┌────────────────────┐
                                              │ RuntimeState       │
                                              │ ────────────       │
                                              │ .completed queue   │
                                              │                    │
                                              │ Bridge.poll()      │
                                              │ → callback         │
                                              │ → refresh UI       │
                                              └────────────────────┘
```

---

## 3. Workflow de détection — Scan complet

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DÉTECTION MULTI-STRATÉGIE                           │
└─────────────────────────────────────────────────────────────────────────┘

PHASE 1 : IMPORT POOLS
──────────────────────

┌─────────────┐
│ zpool list  │──> Pools disponibles (boot_pool, fast_pool, data_pool)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│ zpool import -f -N -o cachefile=none │  (NO-MOUNT !)
└──────┬───────────────────────────────┘
       │
       ▼
   Pools importés, datasets accessibles, AUCUN montage


PHASE 2 : LISTE DATASETS
─────────────────────────

┌────────────────┐
│ zfs list -r -H │──> Liste complète des datasets
└────────┬───────┘
         │
         ▼
    boot_pool/boot      (mountpoint=/boot    dans properties)
    boot_pool/images    (mountpoint=/boot/images)
    fast_pool/overlay   (mountpoint=/overlay)


PHASE 3 : PROBE PAR DATASET (parallèle, max 4 threads)
──────────────────────────────────────────────────────

Pour chaque dataset:

┌─────────────────────────────────────────────────────────────────────┐
│ 1. MONTAGE TEMPORAIRE                                                │
│    mount -t zfs dataset /tmp/fsdeploy-probe-xyz                     │
│    (avec Lock partagé sur pool.probe)                               │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. SCAN STRUCTURE (ROLE_PATTERNS)                                   │
│                                                                       │
│    glob("vmlinuz-*")      → 2 matches  ✅                           │
│    glob("initrd.img-*")   → 2 matches  ✅                           │
│    glob("config-*")       → 2 matches  ✅                           │
│    glob("System.map-*")   → 2 matches  ✅                           │
│                                                                       │
│    Score: 4/4 globs = 1.0                                           │
│    Rôle: boot (prio 10)                                             │
│    Confiance pattern: 100%                                          │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. SCAN CONTENU (MAGIC BYTES)                                       │
│                                                                       │
│    vmlinuz-6.12.0:                                                  │
│      offset 0x000: 7f 45 4c 46  → ELF header  ✅                   │
│      offset 0x202: 48 64 72 53  → "HdrS" (bzImage)  ✅             │
│                                                                       │
│    initrd.img-6.12.0:                                               │
│      offset 0x000: 1f 8b        → gzip header  ✅                  │
│                                                                       │
│    Confiance magic: 100%                                            │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. SCAN APPROFONDI                                                   │
│                                                                       │
│    A. KERNELS (MD5 dedup)                                           │
│       vmlinuz-6.12.0     → MD5: a1b2c3d4...  ✅ Premier            │
│       vmlinuz-6.6.47     → MD5: e5f6g7h8...  ✅ Différent          │
│       vmlinuz-6.12.0.bak → MD5: a1b2c3d4...  ❌ DOUBLON !          │
│                                                                       │
│    B. SQUASHFS (test mount + scan)                                  │
│       rootfs.sfs:                                                   │
│         Magic: hsqs  ✅                                             │
│         mount -t squashfs -o loop,ro rootfs.sfs /tmp/sqfs-test     │
│         Contenu: bin/bash, etc/fstab, usr/bin/  ✅                 │
│         Type: rootfs                                                │
│         Confiance: 95%                                              │
│                                                                       │
│    Confiance approfondie: 95%                                       │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. AGRÉGATION SCORES                                                 │
│                                                                       │
│    Poids:                                                            │
│      - Pattern match  : 40% × 1.00 = 0.40                          │
│      - Magic bytes    : 30% × 1.00 = 0.30                          │
│      - Content scan   : 20% × 0.95 = 0.19                          │
│      - (Partition N/A):  0% × 0.00 = 0.00                          │
│                                                                       │
│    Confiance finale: (0.40 + 0.30 + 0.19) / 0.90 = 0.99 (99%) ✅  │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. DÉMONTAGE PROPRE                                                  │
│    umount /tmp/fsdeploy-probe-xyz                                   │
│    rmdir /tmp/fsdeploy-probe-xyz                                    │
│    Release Lock                                                     │
└─────────────────────────────────────────────────────────────────────┘


PHASE 4 : RÉSULTAT AGRÉGÉ
─────────────────────────

{
  "boot_pool/boot": {
    "role": "boot",
    "confidence": 0.99,
    "signals": {
      "pattern_match": 1.00,
      "magic_bytes": 1.00,
      "content_scan": 0.95
    },
    "kernels": [
      {
        "path": "/mnt/boot/vmlinuz-6.12.0",
        "version": "6.12.0",
        "md5": "a1b2c3d4...",
        "is_duplicate": false
      },
      {
        "path": "/mnt/boot/vmlinuz-6.6.47",
        "version": "6.6.47",
        "md5": "e5f6g7h8...",
        "is_duplicate": false
      },
      {
        "path": "/mnt/boot/vmlinuz-6.12.0.bak",
        "version": "6.12.0",
        "md5": "a1b2c3d4...",
        "is_duplicate": true,
        "duplicate_of": "/mnt/boot/vmlinuz-6.12.0"
      }
    ],
    "squashfs": [
      {
        "path": "/mnt/boot/images/rootfs.sfs",
        "valid": true,
        "mountable": true,
        "content_type": "rootfs",
        "confidence": 0.95
      }
    ]
  }
}
```

---

## 4. Stratégie de montage — Isolation et résolution

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   SYSTÈME LIVE vs MONTAGES FSDEPLOY                      │
└─────────────────────────────────────────────────────────────────────────┘

SYSTÈME LIVE (NE PAS TOUCHER)           MONTAGES FSDEPLOY (ISOLATION)
──────────────────────────────           ──────────────────────────────

/                                        /mnt/
├── boot/                 ← Live ISO     ├── boot/              ← boot_pool/boot
│   ├── vmlinuz           (squashfs)     │   ├── vmlinuz-6.12.0
│   └── initrd.img                       │   ├── initrd.img-6.12.0
│                                        │   └── efi/            ← partition EFI
├── bin/                                 │       └── EFI/
├── etc/                                 │
├── usr/                                 ├── rootfs/            ← overlayfs merged
├── var/                                 │   ├── bin/           (lower: rootfs.sfs)
└── ...                                  │   ├── etc/           (upper: overlay ds)
                                         │   └── ...
    ⚠️ PAS DE MONTAGE ZFS ICI !         │
                                         └── overlay/          ← fast_pool/overlay
                                             ├── upper/
                                             └── work/

                                             ✅ TOUS LES MONTAGES ZFS ICI


WORKFLOW DE MONTAGE
───────────────────

1. DÉTECTION → Rôles identifiés
   
   boot_pool/boot      → boot      (99%)
   boot_pool/images    → squashfs  (95%)
   fast_pool/overlay   → overlay   (85%)


2. PROPOSITIONS par rôle (MOUNT_PROPOSALS)

   boot      → /mnt/boot
   squashfs  → /mnt/boot/images
   overlay   → /mnt/overlay


3. VÉRIFICATION CONFLITS

   Même mountpoint, datasets différents ?
   
   ✅ NON : boot_pool/boot       → /mnt/boot
            boot_pool/images     → /mnt/boot/images  (sous-répertoire)
            fast_pool/overlay    → /mnt/overlay
   
   Si conflit détecté:
     → Modification manuelle dans MountsScreen
     → OU erreur dans CoherenceScreen


4. MONTAGE CANONIQUE (forme standard)

   mkdir -p /mnt/boot
   mount -t zfs boot_pool/boot /mnt/boot
   
   mkdir -p /mnt/boot/images
   mount -t zfs boot_pool/images /mnt/boot/images
   
   mkdir -p /mnt/overlay
   mount -t zfs fast_pool/overlay /mnt/overlay
   
   ⚠️ TOUJOURS mount -t zfs (pas zfs mount)
   → Ignore la property mountpoint
   → Fonctionne avec mountpoint=legacy


5. VÉRIFICATION POST-MONTAGE

   grep "boot_pool/boot" /proc/mounts
   → boot_pool/boot /mnt/boot zfs rw,xattr,noacl 0 0  ✅
   
   Property mountpoint INTACTE:
   zfs get -H -o value mountpoint boot_pool/boot
   → /boot  (inchangée !)
```

---

## 5. Flux de données complet — Du boot au stream

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      FLUX DE DONNÉES COMPLET                             │
└─────────────────────────────────────────────────────────────────────────┘

ÉTAPE 1 : BOOT DEBIAN LIVE
───────────────────────────
    │
    ▼
┌────────────────────┐
│ launch.sh          │──> APT + DKMS + venv + git
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ python3 -m fsdeploy│──> Daemon start
└────────┬───────────┘
         │
         ▼

ÉTAPE 2 : DÉTECTION
────────────────────
    │
    ▼
┌────────────────────────────────────┐
│ Import pools (-N)                  │
│ Liste datasets                     │
│ Probe (mount temp + scan + umount) │
│ Détection partitions               │
└────────┬───────────────────────────┘
         │
         ▼
    Résultats :
    - boot_pool/boot (boot, 99%)
    - boot_pool/images (squashfs, 95%)
    - fast_pool/overlay (overlay, 85%)
    - /dev/nvme0n1p1 (efi)


ÉTAPE 3 : MONTAGES
───────────────────
    │
    ▼
┌────────────────────────────────────┐
│ Propositions par rôle              │
│ Vérification conflits              │
│ mount -t zfs dataset /mnt/...      │
│ Vérification post-montage          │
└────────┬───────────────────────────┘
         │
         ▼
    État :
    - boot_pool/boot     → /mnt/boot       ✅
    - boot_pool/images   → /mnt/boot/images ✅
    - fast_pool/overlay  → /mnt/overlay    ✅
    - /dev/nvme0n1p1     → /mnt/boot/efi   ✅


ÉTAPE 4 : KERNEL + INITRAMFS
─────────────────────────────
    │
    ▼
┌────────────────────────────────────┐
│ Sélection kernel (ou compilation)  │
│   vmlinuz-6.12.0 ← choisi          │
│                                     │
│ Génération initramfs               │
│   Type: zbm / minimal / stream     │
│   dracut -f initrd.img-6.12.0      │
│   (ou cpio custom)                 │
└────────┬───────────────────────────┘
         │
         ▼
    Fichiers générés :
    - /mnt/boot/vmlinuz-6.12.0       ✅
    - /mnt/boot/initrd.img-6.12.0    ✅


ÉTAPE 5 : PRESETS
──────────────────
    │
    ▼
┌────────────────────────────────────┐
│ Création preset JSON               │
│ {                                   │
│   "kernel": "$BOOT/vmlinuz-6.12.0",│
│   "initramfs": "$BOOT/initrd...",  │
│   "rootfs": "$BOOT/images/rootfs.sfs",│
│   "overlay": "fast_pool/overlay",  │
│   "modules": "$BOOT/modules",      │
│   "python_sfs": "$BOOT/python.sfs" │
│ }                                   │
│                                     │
│ Enregistré dans boot_pool/presets/ │
└────────┬───────────────────────────┘
         │
         ▼


ÉTAPE 6 : COHÉRENCE
────────────────────
    │
    ▼
┌────────────────────────────────────┐
│ Vérifications :                    │
│   ✅ Boot pool importable          │
│   ✅ Kernel valide (ELF + taille)  │
│   ✅ Initramfs valide (gzip)       │
│   ✅ Partition EFI montée          │
│   ✅ Preset complet                │
│   ✅ Squashfs valide (test mount)  │
│   ✅ Overlay dataset accessible    │
│                                     │
│ Rapport : SYSTÈME VALIDE ✅        │
└────────┬───────────────────────────┘
         │
         ▼


ÉTAPE 7 : INSTALLATION ZBM
───────────────────────────
    │
    ▼
┌────────────────────────────────────┐
│ zbm-install                        │
│   --kernel vmlinuz-6.12.0          │
│   --initramfs initrd.img-6.12.0    │
│   --pool boot_pool                 │
│                                     │
│ efibootmgr                         │
│   --create --label "ZFSBootMenu"   │
│   --disk /dev/nvme0n1              │
│   --part 1                          │
│   --loader '\EFI\zbm\vmlinuz.efi'  │
└────────┬───────────────────────────┘
         │
         ▼


ÉTAPE 8 : REBOOT
─────────────────
    │
    ▼
┌────────────────────┐
│ ZFSBootMenu        │
│ ───────────        │
│ Import boot_pool   │
│ Liste presets      │
│ Sélection UI       │
└────────┬───────────┘
         │
         ├──> Preset "normal"
         │    │
         │    ▼
         │    kexec vmlinuz-6.12.0
         │    initrd.img-6.12.0
         │    │
         │    ▼
         │    Mount overlayfs
         │    (lower: rootfs.sfs,
         │     upper: fast_pool/overlay)
         │    │
         │    ▼
         │    pivot_root /mnt/merged
         │    │
         │    ▼
         │    BOOT OS ✅
         │
         └──> Preset "stream"
              │
              ▼
              kexec vmlinuz-6.12.0
              initrd-stream.img
              │
              ▼
              Réseau DHCP
              │
              ▼
              Python env (from sfs)
              │
              ▼
              ffmpeg stream YouTube
              │
              ▼
              STREAM LIVE ✅
```

---

## Conclusion

Ces graphiques illustrent :

1. **Architecture complète** : daemon → scheduler → TUI → bus
2. **Pipeline événementiel** : Event → Intent → Task → Execution
3. **Détection multi-stratégie** : patterns + magic + MD5 + squashfs
4. **Stratégie de montage** : isolation `/mnt/`, résolution conflits
5. **Flux de données** : boot → détection → montage → ZBM → stream

**Tous ces schémas sont intégrés dans la documentation principale.**

---

**Document fsdeploy**  
**Version** : 2.0  
**Date** : 21 mars 2026
