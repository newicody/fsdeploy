# Import ZFS vs Mount manuel — fsdeploy

**Document technique** — Clarification mountpoints ZFS et montage manuel

---

## Question fondamentale

**Peut-on importer des pools avec leurs mountpoints ZFS configurés, puis monter manuellement les datasets ailleurs ?**

**Réponse : OUI, sans aucun problème.**

---

## Principes ZFS

### 1. Mountpoint property vs mount actuel

ZFS distingue **deux concepts** :

```bash
# Property ZFS (configurée sur le dataset)
zfs get mountpoint tank/home
# NAME       PROPERTY    VALUE      SOURCE
# tank/home  mountpoint  /home      local

# Montage effectif actuel (peut être différent !)
mount | grep tank/home
# tank/home on /mnt/home type zfs (rw,xattr,noacl)
```

**La property `mountpoint`** :
- Stockée dans les metadata ZFS
- Utilisée par `zfs mount` sans arguments
- N'empêche PAS un montage manuel ailleurs

**Le montage effectif** :
- Ce qui apparaît dans `/proc/mounts`
- Contrôlé par `mount -t zfs` ou `zfs mount -o mountpoint=...`
- Peut être totalement différent de la property

### 2. Import avec no-mount

fsdeploy importe **tous les pools** avec l'option `-N` (no-mount) :

```bash
# Import sans monter automatiquement
zpool import -f -N -o cachefile=none boot_pool
zpool import -f -N -o cachefile=none fast_pool
zpool import -f -N -o cachefile=none data_pool
```

**Conséquences** :
- Pools importés et accessibles
- Datasets listables avec `zfs list`
- Properties lisibles avec `zfs get`
- **AUCUN dataset monté automatiquement**
- Pas de conflit avec mountpoints existants du live

### 3. Mount manuel post-import

Après import `-N`, on monte où on veut :

```bash
# Dataset a mountpoint=/boot dans ses properties
zfs get -H -o value mountpoint boot_pool/boot
# /boot

# Mais on le monte ailleurs manuellement
mount -t zfs boot_pool/boot /mnt/boot

# Vérification
mount | grep boot_pool/boot
# boot_pool/boot on /mnt/boot type zfs (rw,xattr,noacl)

# La property n'a pas changé
zfs get -H -o value mountpoint boot_pool/boot
# /boot (toujours !)
```

**Résultat** : dataset monté sur `/mnt/boot`, property toujours `/boot`. **Aucun conflit.**

---

## Workflow fsdeploy détaillé

### Phase 1 : Import pools (no-mount)

```python
@security.pool.import
class PoolImportTask(Task):
    def run(self):
        pool = self.params["pool"]
        
        # Import SANS montage automatique
        self.run_cmd(
            f"zpool import -f -N -o cachefile=none {pool}",
            sudo=True
        )
        
        # Vérifier que le pool est importé
        r = self.run_cmd(f"zpool list -H -o name {pool}", check=False)
        imported = r.success and pool in r.stdout
        
        return {"pool": pool, "imported": imported}
```

**État après import** :
```bash
zpool list
# NAME        SIZE  ALLOC   FREE  CKPOINT  EXPANDSZ   FRAG    CAP  DEDUP  HEALTH  ALTROOT
# boot_pool  100G   20G    80G        -         -     15%    20%  1.00x  ONLINE  -
# fast_pool  500G  200G   300G        -         -     25%    40%  1.00x  ONLINE  -
# data_pool    5T    2T     3T        -         -     18%    40%  1.00x  ONLINE  -

zfs list
# NAME                    USED  AVAIL  REFER  MOUNTPOINT
# boot_pool              20.0G  78.5G    96K  none
# boot_pool/boot         15.0G  78.5G  15.0G  /boot         ← property
# boot_pool/images        5.0G  78.5G   5.0G  /boot/images  ← property
# fast_pool             200.0G   296G    96K  none
# fast_pool/overlay     200.0G   296G  200G  /overlay       ← property

mount | grep zfs
# (vide — aucun dataset ZFS monté)
```

### Phase 2 : Détection et probe

```python
@security.detect.dataset
class DatasetProbeTask(Task):
    def run(self):
        dataset = self.params["dataset"]
        
        # Montage temporaire pour probe
        temp_mount = tempfile.mkdtemp(prefix="fsdeploy-probe-")
        
        # IMPORTANT : mount manuel, ignore la property mountpoint
        self.run_cmd(
            f"mount -t zfs {dataset} {temp_mount}",
            sudo=True
        )
        
        # Probe : scan fichiers, glob patterns
        role, confidence = self._probe_content(temp_mount)
        
        # Démontage propre
        self.run_cmd(f"umount {temp_mount}", sudo=True)
        os.rmdir(temp_mount)
        
        return {"dataset": dataset, "role": role, "confidence": confidence}
    
    def _probe_content(self, path):
        # Scan contre ROLE_PATTERNS
        for pattern in ROLE_PATTERNS:
            matches = [g for g in pattern["globs"] if list(Path(path).glob(g))]
            if len(matches) >= pattern["min"]:
                return pattern["role"], min(len(matches)/len(pattern["globs"]), 1.0)
        return "data", 0.0
```

**État après probe** :
```bash
# Montages temporaires (créés puis supprimés)
/tmp/fsdeploy-probe-xyz123 ← boot_pool/boot (monté puis démonté)
/tmp/fsdeploy-probe-abc456 ← boot_pool/images (monté puis démonté)

# Résultat détection :
{
  "boot_pool/boot": {"role": "boot", "confidence": 0.95},
  "boot_pool/images": {"role": "squashfs", "confidence": 0.90},
  "fast_pool/overlay": {"role": "overlay", "confidence": 0.85}
}

# Aucun dataset monté de façon permanente
mount | grep zfs
# (vide)
```

### Phase 3 : Montage manuel final

```python
@security.dataset.mount
class DatasetMountTask(Task):
    def run(self):
        dataset = self.params["dataset"]
        mountpoint = self.params["mountpoint"]
        
        # Vérifier si déjà monté
        r = self.run_cmd(f"zfs get -H -o value mounted {dataset}", check=False)
        if r.success and r.stdout.strip() == "yes":
            # Déjà monté (par probe ou autre) → démonter d'abord
            self.run_cmd(f"umount {dataset}", sudo=True, check=False)
        
        # Mount manuel sur le mountpoint choisi
        Path(mountpoint).mkdir(parents=True, exist_ok=True)
        self.run_cmd(
            f"mount -t zfs {dataset} {mountpoint}",
            sudo=True
        )
        
        return {"dataset": dataset, "mountpoint": mountpoint, "mounted": True}
```

**État après montage manuel** :
```bash
mount | grep zfs
# boot_pool/boot on /mnt/boot type zfs (rw,xattr,noacl)
# boot_pool/images on /mnt/boot/images type zfs (rw,xattr,noacl)
# fast_pool/overlay on /mnt/overlay type zfs (rw,xattr,noacl)

# Properties inchangées
zfs get -H -o value mountpoint boot_pool/boot
# /boot (toujours la property originale !)

# Mais montage effectif différent
findmnt /mnt/boot
# TARGET     SOURCE          FSTYPE OPTIONS
# /mnt/boot  boot_pool/boot  zfs    rw,xattr,noacl
```

---

## Pourquoi ça fonctionne

### 1. `-N` (no-mount) à l'import

```bash
zpool import -N boot_pool
```

**Effet** : 
- Pool importé, datasets accessibles
- Property `mountpoint` lue mais **pas appliquée**
- Aucun montage automatique
- Pas de conflit avec `/boot` du live

### 2. `mount -t zfs` manuel ignore la property

```bash
# Property dit /boot
zfs get mountpoint boot_pool/boot
# mountpoint  /boot  local

# Mais mount -t zfs permet de monter ailleurs
mount -t zfs boot_pool/boot /mnt/boot

# Résultat : monté sur /mnt/boot, property /boot intacte
```

**Différence avec `zfs mount`** :

```bash
# zfs mount (SANS arguments) utilise la property
zfs mount boot_pool/boot
# → monte sur /boot (property mountpoint)
# ⚠️ CONFLIT POTENTIEL avec le live !

# mount -t zfs (AVEC mountpoint explicite) ignore la property
mount -t zfs boot_pool/boot /mnt/boot
# → monte sur /mnt/boot (argument explicite)
# ✅ PAS DE CONFLIT
```

### 3. Locks thread-safe pendant probe

```python
class DatasetProbeTask(Task):
    def required_locks(self):
        dataset = self.params["dataset"]
        pool = dataset.split("/")[0]
        return [Lock(f"pool.{pool}.probe", owner_id=str(self.id), exclusive=False)]
```

**Locks partagés** : plusieurs probes simultanées sur le même pool (non-bloquantes).

**Locks exclusifs** : montage/démontage (bloquent autres opérations sur le dataset).

---

## Cas limites et edge cases

### Cas 1 : Dataset déjà monté (par erreur)

```bash
# Quelqu'un a fait zfs mount boot_pool/boot
# → monté sur /boot (property)

# fsdeploy tente mount -t zfs boot_pool/boot /mnt/boot
# → ERREUR : dataset already mounted
```

**Solution fsdeploy** :

```python
# Vérifier si monté
r = self.run_cmd("zfs get -H -o value mounted {dataset}")
if r.stdout.strip() == "yes":
    # Démonter d'abord
    self.run_cmd(f"umount {dataset}", sudo=True)
    
# Puis monter sur /mnt/boot
self.run_cmd(f"mount -t zfs {dataset} /mnt/boot", sudo=True)
```

### Cas 2 : Property mountpoint=legacy

```bash
zfs get mountpoint boot_pool/boot
# mountpoint  legacy  local
```

**Comportement** :
- `zfs mount boot_pool/boot` → **échoue silencieusement** (bug ZFS connu)
- `mount -t zfs boot_pool/boot /mnt/boot` → **fonctionne parfaitement**

**C'est pourquoi fsdeploy utilise TOUJOURS `mount -t zfs`.**

### Cas 3 : Mountpoint property = none

```bash
zfs get mountpoint boot_pool/boot
# mountpoint  none  local
```

**Comportement** :
- `zfs mount boot_pool/boot` → erreur "cannot mount: mountpoint is none"
- `mount -t zfs boot_pool/boot /mnt/boot` → **fonctionne**

### Cas 4 : Import pool déjà importé

```bash
zpool import boot_pool
# cannot import 'boot_pool': pool is already imported
```

**Solution fsdeploy** :

```python
# Vérifier si déjà importé
r = self.run_cmd("zpool list -H -o name", check=False)
if pool in r.stdout:
    # Déjà importé → skip import
    return {"pool": pool, "already_imported": True}

# Sinon, importer
self.run_cmd(f"zpool import -f -N {pool}", sudo=True)
```

---

## Comparaison des approches

### Approche A : zfs mount (property mountpoint)

```bash
# Import AVEC montage auto
zpool import boot_pool
# → tous les datasets se montent sur leurs mountpoints (properties)
# boot_pool/boot → /boot  ⚠️ CONFLIT avec le live !

# Puis il faudrait tout démonter et remonter
umount /boot  # ⚠️ peut casser le live !
mount -t zfs boot_pool/boot /mnt/boot
```

**Problèmes** :
- Montages automatiques créent des conflits
- Nécessite démontage/remontage
- Risque de casser le live

### Approche B : import -N + mount manuel (fsdeploy)

```bash
# Import SANS montage
zpool import -N boot_pool
# → pool importé, datasets listables, RIEN de monté

# Montage manuel où on veut
mount -t zfs boot_pool/boot /mnt/boot
# → monté sur /mnt/boot, pas de conflit
```

**Avantages** :
- Aucun conflit avec le live
- Contrôle total sur les mountpoints
- Properties ZFS intactes (pas de modification)
- Nettoyage propre (`umount -R /mnt`)

---

## Vérification de l'état

### Commandes utiles

```bash
# Liste des pools importés
zpool list -H -o name,health,altroot

# Liste des datasets (avec properties mountpoint)
zfs list -H -o name,mountpoint,mounted

# Montages effectifs
mount | grep zfs
findmnt -t zfs

# Vérifier un dataset spécifique
zfs get -H -o value mountpoint,mounted boot_pool/boot

# Historique des montages (via /proc/mounts)
cat /proc/mounts | grep zfs
```

### Script de diagnostic

```bash
#!/bin/bash
# fsdeploy-mount-diagnostic.sh

echo "=== Pools importés ==="
zpool list

echo -e "\n=== Datasets (properties) ==="
zfs list -o name,mountpoint,mounted

echo -e "\n=== Montages effectifs ==="
mount | grep zfs

echo -e "\n=== Montages dans /mnt/ ==="
findmnt /mnt

echo -e "\n=== Conflit potentiel /boot ==="
if mount | grep -q "on /boot type zfs"; then
    echo "⚠️ WARNING : un dataset ZFS est monté sur /boot (conflit avec live !)"
else
    echo "✅ OK : pas de dataset ZFS sur /boot"
fi

echo -e "\n=== Datasets non montés ==="
zfs list -H -o name,mounted | grep "no$"
```

---

## Recommandations fsdeploy

### 1. Toujours importer avec -N

```python
POOL_IMPORT_CMD = "zpool import -f -N -o cachefile=none {pool}"
```

### 2. Toujours monter avec mount -t zfs

```python
MOUNT_CMD = "mount -t zfs {dataset} {mountpoint}"
# JAMAIS : zfs mount {dataset}
```

### 3. Vérifier mounted avant montage

```python
r = self.run_cmd("zfs get -H -o value mounted {dataset}")
if r.stdout.strip() == "yes":
    # Démonter d'abord
    self.run_cmd(f"umount {dataset}", sudo=True)
```

### 4. Locks thread-safe

```python
def required_locks(self):
    return [Lock(f"dataset.{dataset}", exclusive=True)]
```

### 5. Vérification post-montage via /proc/mounts

```python
mounts = Path("/proc/mounts").read_text()
for line in mounts.splitlines():
    dev, mp = line.split()[:2]
    if dev == dataset and mp == expected_mountpoint:
        return True
```

---

## Conclusion

### Réponse à la question initiale

**Peut-on importer des pools avec mountpoints configurés, puis monter manuellement ailleurs ?**

**OUI, absolument.** C'est exactement ce que fait fsdeploy :

1. `zpool import -N` → import sans montage auto
2. Probe avec montages temporaires
3. `mount -t zfs <dataset> <mountpoint>` → montage manuel sur `/mnt/`
4. Properties ZFS intactes, montages effectifs contrôlés

### Aucun problème, aucun conflit

- Le live reste intact (`/boot`, `/`)
- Les datasets ZFS se montent dans `/mnt/`
- Properties `mountpoint` inchangées
- Nettoyage propre avec `umount -R /mnt`

### La clé : mount -t zfs avec mountpoint explicite

```bash
# Cette commande ignore la property mountpoint
mount -t zfs boot_pool/boot /mnt/boot

# Et monte le dataset exactement où on veut
# Même si property mountpoint=/boot
```

---

**Document technique fsdeploy**  
**Version** : 1.0  
**Date** : 21 mars 2026
