# Stratégie de montage — fsdeploy

**Document technique** — Résolution des conflits mountpoints et gestion du live

---

## Problématique

Le système live Debian a ses propres montages :
- `/boot` : squashfs du live (ISO ou USB)
- `/` : overlayfs (tmpfs upper + squashfs lower)
- `/dev`, `/proc`, `/sys` : filesystems virtuels

**fsdeploy** doit monter les datasets ZFS du système cible **sans interférer** avec le live.

---

## Stratégie adoptée : isolation dans `/mnt/`

### Principe

**Tous les montages fsdeploy se font dans `/mnt/`**, jamais dans `/boot` ou `/` du live.

```
Système live (ne pas toucher) :
  /boot             ← live squashfs
  /                 ← live overlayfs

Montages fsdeploy (isolation) :
  /mnt/boot         ← boot_pool/boot (dataset détecté boot)
  /mnt/boot/efi     ← partition EFI
  /mnt/rootfs       ← overlayfs merged (système cible)
  /mnt/overlay      ← dataset overlay (upper layer)
```

### Bénéfices

1. **Pas de conflit** : `/mnt/boot` ≠ `/boot`
2. **Montages multiples** : plusieurs datasets peuvent être montés simultanément
3. **Nettoyage propre** : `umount -R /mnt` démonte tout sans affecter le live
4. **Sécurité** : le live reste bootable même si fsdeploy plante

---

## Propositions de montage par rôle

Définies dans `lib/ui/screens/mounts.py` :

```python
MOUNT_PROPOSALS = {
    "boot": "/mnt/boot",
    "efi": "/mnt/boot/efi",
    "rootfs": "/mnt/rootfs",
    "kernel": "/mnt/boot",           # ⚠️ même mountpoint que boot
    "modules": "/mnt/boot/modules",  # sous-répertoire de boot
    "initramfs": "/mnt/boot",        # ⚠️ même mountpoint que boot
    "squashfs": "/mnt/boot/images",  # sous-répertoire de boot
    "overlay": "/mnt/overlay",
    "python_env": "/mnt/boot/python",
}
```

### Cas 1 : même dataset, plusieurs rôles

**Scénario** : `boot_pool/boot` contient kernel + initramfs + boot files

```
Dataset détecté :
  boot_pool/boot
    ├── role: boot (confidence: 0.95)
    ├── role: kernel (confidence: 0.80)
    └── role: initramfs (confidence: 0.80)

Montage :
  mount -t zfs boot_pool/boot /mnt/boot

Résultat :
  /mnt/boot/vmlinuz-6.12.0        ← kernel
  /mnt/boot/initrd.img-6.12.0     ← initramfs
  /mnt/boot/config-6.12.0         ← boot
```

**Résolution** : **un seul montage**. Le dataset contient tous les rôles.

### Cas 2 : datasets différents, même mountpoint proposé

**Scénario** : kernel dans `boot_pool/kernel`, initramfs dans `boot_pool/initramfs`

```
Datasets détectés :
  boot_pool/boot      → role: boot      → mountpoint: /mnt/boot
  boot_pool/kernel    → role: kernel    → mountpoint: /mnt/boot  ⚠️
  boot_pool/initramfs → role: initramfs → mountpoint: /mnt/boot  ⚠️

Conflit : 3 datasets → 1 mountpoint
```

**Résolution** :

**Option A** : L'utilisateur modifie les mountpoints dans MountsScreen :

```
boot_pool/boot      → /mnt/boot
boot_pool/kernel    → /mnt/boot/kernel      (modifié)
boot_pool/initramfs → /mnt/boot/initramfs   (modifié)
```

**Option B** : Détection d'erreur de cohérence (signalée dans CoherenceScreen) :

```
❌ ERREUR : Plusieurs datasets veulent se monter sur /mnt/boot
   - boot_pool/boot (boot)
   - boot_pool/kernel (kernel)
   - boot_pool/initramfs (initramfs)

Action requise : Modifier les mountpoints ou corriger l'architecture ZFS
```

### Cas 3 : sous-répertoires

**Scénario** : modules dans un sous-répertoire de boot

```
Dataset :
  boot_pool/boot → /mnt/boot

Proposition :
  modules → /mnt/boot/modules

Montage :
  mount -t zfs boot_pool/boot /mnt/boot
  mkdir -p /mnt/boot/modules
  # modules déjà présents dans boot_pool/boot/modules/
```

**Résolution** : **pas de montage supplémentaire** si `modules` est un sous-répertoire du dataset `boot`.

Si `modules` est un **dataset séparé** (`boot_pool/modules`), alors :

```
mount -t zfs boot_pool/boot /mnt/boot
mount -t zfs boot_pool/modules /mnt/boot/modules  # bind mount
```

---

## Code de montage

### Forme canonique : `mount -t zfs`

**Bug connu** : `zfs mount <dataset>` échoue silencieusement pour `mountpoint=legacy`.

**Solution** : **toujours utiliser** `mount -t zfs <dataset> <mountpoint>`.

```python
@security.dataset.mount
class DatasetMountTask(Task):
    def run(self):
        dataset = self.params["dataset"]
        mountpoint = self.params["mountpoint"]
        
        # Vérifier mountpoint property ZFS
        r = self.run_cmd(f"zfs get -H -o value mountpoint {dataset}", check=False)
        mp_value = r.stdout.strip() if r.success else ""
        
        if mp_value in ("legacy", "none") or mountpoint:
            # FORME CANONIQUE (legacy ou montage custom)
            Path(mountpoint).mkdir(parents=True, exist_ok=True)
            self.run_cmd(f"mount -t zfs {dataset} {mountpoint}", sudo=True)
        else:
            # Standard ZFS mount (utilise la property mountpoint)
            # ⚠️ Peut échouer silencieusement pour legacy !
            self.run_cmd(f"zfs mount {dataset}", sudo=True)
            mountpoint = mp_value
        
        return {"dataset": dataset, "mountpoint": mountpoint, "mounted": True}
```

### Vérification post-montage

```python
@security.mount.verify
class MountVerifyTask(Task):
    def run(self):
        dataset = self.params["dataset"]
        mountpoint = self.params["mountpoint"]
        
        # Vérifier /proc/mounts (source de vérité)
        try:
            mounts = Path("/proc/mounts").read_text()
            for line in mounts.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == dataset:
                    actual_mp = parts[1]
                    verified = (actual_mp == mountpoint)
                    return {
                        "dataset": dataset,
                        "verified": verified,
                        "actual": actual_mp,
                        "expected": mountpoint,
                    }
        except OSError:
            pass
        
        # Fallback : zfs get mountpoint
        r = self.run_cmd(f"zfs get -H -o value mountpoint {dataset}", check=False)
        if r.success:
            mp = r.stdout.strip()
            if mp and mp not in ("-", "none"):
                # Vérifier avec mountpoint -q
                r2 = self.run_cmd(f"mountpoint -q {mp}", check=False)
                verified = r2.success and (mp == mountpoint)
                return {
                    "dataset": dataset,
                    "verified": verified,
                    "actual": mp,
                    "expected": mountpoint,
                }
        
        return {"dataset": dataset, "verified": False, "error": "not mounted"}
```

---

## Workflow de montage dans la TUI

### MountsScreen

```
┌─────────────────────────────────────────────────────────────────┐
│  Dataset            │ Rôle      │ Actuel │ Proposé    │ Monté  │
├─────────────────────────────────────────────────────────────────┤
│  boot_pool/boot     │ boot      │ -      │ /mnt/boot  │ ✅     │
│  boot_pool/images   │ squashfs  │ -      │ /mnt/boot/images │ - │
│  fast_pool/overlay  │ overlay   │ -      │ /mnt/overlay     │ - │
└─────────────────────────────────────────────────────────────────┘

Actions :
  [m] Monter sélectionné   [u] Démonter   [e] Modifier mountpoint
  [a] Tout monter          [v] Vérifier   [Enter] Suivant
```

1. **Détection** : datasets + probe → rôles + confiance
2. **Proposition** : `MOUNT_PROPOSALS[role]`
3. **Modification** : utilisateur peut changer le mountpoint
4. **Montage** : `bridge.emit("mount.request", dataset=..., mountpoint=...)`
5. **Vérification** : `bridge.emit("mount.verify", dataset=..., mountpoint=...)`

### Flux event-driven

```python
# 1. Utilisateur appuie sur 'a' (monter tous)
def action_mount_all(self):
    for entry in self._entries:
        if not entry["mounted"] and entry["proposed"]:
            bridge.emit("mount.request",
                        dataset=entry["dataset"],
                        mountpoint=entry["proposed"])

# 2. Scheduler reçoit l'event
Event(name="mount.request", params={"dataset": "boot_pool/boot", "mountpoint": "/mnt/boot"})

# 3. Handler crée l'intent
@register_intent("mount.request")
class MountRequestIntent(Intent):
    def build_tasks(self):
        return [DatasetMountTask(params=self.params)]

# 4. Task s'exécute
@security.dataset.mount
class DatasetMountTask(Task):
    def run(self):
        # mount -t zfs boot_pool/boot /mnt/boot
        ...

# 5. Résultat revient via bridge.poll()
bridge.poll()  # Vérifie state.completed → fire callback → refresh UI
```

---

## Gestion des conflits : matrice de décision

| Situation | Dataset 1 | Dataset 2 | Mountpoint proposé | Action |
|-----------|-----------|-----------|-------------------|--------|
| **Même dataset, plusieurs rôles** | boot_pool/boot (boot+kernel+initramfs) | - | /mnt/boot | ✅ Un seul montage |
| **Datasets différents, même role** | boot_pool/boot (boot) | fast_pool/boot (boot) | /mnt/boot | ❌ Erreur (2 datasets boot ?) |
| **Datasets différents, roles différents, même mountpoint** | boot_pool/boot (boot) | boot_pool/kernel (kernel) | /mnt/boot | ⚠️ Modifier mountpoint ou erreur |
| **Sous-répertoire d'un dataset monté** | boot_pool/boot | boot_pool/boot/modules/ | /mnt/boot/modules | ✅ Pas de montage (déjà dans boot) |
| **Dataset séparé, sous-répertoire proposé** | boot_pool/boot | boot_pool/modules (dataset) | /mnt/boot/modules | ✅ Bind mount |

---

## Exemples pratiques

### Exemple 1 : Architecture simple

```
Pools :
  boot_pool (NVMe-A)
  fast_pool (NVMe-B)

Datasets :
  boot_pool/boot     → boot + kernel + initramfs
  boot_pool/images   → squashfs
  fast_pool/overlay  → overlay

Montages :
  mount -t zfs boot_pool/boot /mnt/boot
  # kernel et initramfs sont dans boot_pool/boot/
  # squashfs dans boot_pool/boot/images/ (pas besoin de monter boot_pool/images)
  mount -t zfs fast_pool/overlay /mnt/overlay
```

### Exemple 2 : Architecture complexe

```
Pools :
  boot_pool (NVMe-A)
  fast_pool (NVMe-B)

Datasets :
  boot_pool/boot      → boot files uniquement
  boot_pool/kernel    → kernels séparés
  boot_pool/initramfs → initramfs séparés
  boot_pool/images    → squashfs
  fast_pool/overlay   → overlay

Montages proposés (CONFLICT) :
  boot_pool/boot      → /mnt/boot
  boot_pool/kernel    → /mnt/boot     ❌ CONFLIT
  boot_pool/initramfs → /mnt/boot     ❌ CONFLIT

Solution utilisateur :
  boot_pool/boot      → /mnt/boot
  boot_pool/kernel    → /mnt/boot/kernel      (modifié)
  boot_pool/initramfs → /mnt/boot/initramfs   (modifié)
  boot_pool/images    → /mnt/boot/images
  fast_pool/overlay   → /mnt/overlay

Montages finaux :
  mount -t zfs boot_pool/boot /mnt/boot
  mount -t zfs boot_pool/kernel /mnt/boot/kernel
  mount -t zfs boot_pool/initramfs /mnt/boot/initramfs
  mount -t zfs boot_pool/images /mnt/boot/images
  mount -t zfs fast_pool/overlay /mnt/overlay
```

---

## Vérification de cohérence

Le **CoherenceScreen** détecte les conflits et erreurs :

```python
def check_mount_conflicts(self):
    """Détecte les conflits de montage."""
    conflicts = []
    mountpoints = {}
    
    for entry in self.datasets:
        ds = entry["dataset"]
        mp = entry["proposed"]
        role = entry["role"]
        
        if mp in mountpoints:
            # Conflit : même mountpoint pour 2 datasets
            other_ds, other_role = mountpoints[mp]
            
            if ds != other_ds:
                conflicts.append({
                    "type": "mount_conflict",
                    "mountpoint": mp,
                    "datasets": [ds, other_ds],
                    "roles": [role, other_role],
                    "severity": "error",
                })
        else:
            mountpoints[mp] = (ds, role)
    
    return conflicts
```

**Rapport** :

```
┌─────────────────────────────────────────────────────────────┐
│  Vérification de cohérence                                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ✅ Pools : 2/2 importés                                     │
│  ✅ Boot pool : boot_pool détecté                            │
│  ✅ Partition EFI : /dev/nvme0n1p1 montée sur /mnt/boot/efi │
│                                                               │
│  ❌ ERREUR : Conflit de montage                              │
│     Mountpoint : /mnt/boot                                   │
│     Datasets :                                               │
│       - boot_pool/boot (role: boot)                          │
│       - boot_pool/kernel (role: kernel)                      │
│                                                               │
│  Action requise :                                            │
│    Retourner à l'écran Montages (m) et modifier             │
│    les mountpoints pour éviter le conflit.                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Nettoyage

Démontage récursif propre :

```bash
# Dans la TUI : écran Debug (x) → bouton "Tout démonter"
# Ou via CLI :
python3 -m fsdeploy umount --all

# Ou manuel :
sudo umount -R /mnt
```

**Ordre de démontage** (inverse du montage) :

```
1. /mnt/boot/efi
2. /mnt/boot/images
3. /mnt/boot/kernel
4. /mnt/boot/initramfs
5. /mnt/boot
6. /mnt/overlay
7. /mnt/rootfs (overlayfs merged)
```

---

## Conclusion

### Principes de la stratégie de montage

1. **Isolation** : tous les montages dans `/mnt/`, jamais dans `/boot` ou `/` du live
2. **Détection intelligente** : probe par contenu, pas par nom hardcodé
3. **Flexibilité** : l'utilisateur peut modifier les mountpoints proposés
4. **Vérification** : post-montage check via `/proc/mounts`
5. **Cohérence** : détection des conflits avant installation ZBM
6. **Forme canonique** : `mount -t zfs <dataset> <mountpoint>` toujours
7. **Thread-safe** : locks sur datasets pendant montage/démontage

### Pas de conflit avec le live

- `/boot` du live ≠ `/mnt/boot` de fsdeploy
- Le live reste intact et bootable
- Nettoyage propre avec `umount -R /mnt`

---

**Document technique fsdeploy**  
**Version** : 1.0  
**Date** : 21 mars 2026
