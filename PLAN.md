# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~23 510 lignes Python, 67 intents, 23 écrans (tous câblés)
> **Tâche active** : **23.1** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 67 intents, 33 task implementations, launch.sh, multi-init |
| 22.1 | Fix __main__.py (import fsdeploy.cli) |
| 19.2 | Tous les 23 écrans câblés — 0 violation architecture |
| 20.1-3 | Nettoyage complet |
| 17.1 | SecurityResolver 4 niveaux + intégration executor |
| 21.1, 10.5a+b, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 23.1

Voir `add.md`.

---

## Phase 23 : Isolation (cgroups + namespaces)

### Analyse : ce que ça apporte à fsdeploy

| Mécanisme | Cas d'usage fsdeploy | Bénéfice |
|-----------|---------------------|----------|
| **Mount namespace** | `DatasetProbeTask` fait des mounts temporaires pour scanner les datasets. Si crash entre mount et umount → mount leak. Un mount namespace isole ces mounts : quand le process fils termine, tous ses mounts disparaissent automatiquement. | **Anti-leak mounts** — plus de mounts orphelins après crash |
| **Mount namespace** | `rootfs/switch.py` fait du switch à chaud. Tester dans un namespace avant de committer sur le système réel. | **Dry-run réaliste** — tester un switch sans affecter le système |
| **cgroup cpu/mem** | `KernelCompileTask` peut consommer 100% CPU pendant des heures. Un cgroup limite l'impact sur le reste du système. | **Resource governance** — compilation kernel ne freeze plus la machine |
| **cgroup cpu/mem** | ZFS scrub/resilver peuvent saturer les I/O. | **I/O throttle** — opérations ZFS lourdes bridées |
| **PID namespace** | Isoler les processus enfants (compilation, ffmpeg stream) pour kill propre. | **Cleanup garanti** — plus de processus orphelins |
| **User namespace** | Exécuter certaines tasks avec "fake root" au lieu de vrai sudo. Réduit la surface sudoers. | **Least privilege** — moins de sudo réel |

### Tâches planifiées

| ID | Description | Priorité |
|----|-------------|----------|
| **23.1** | Créer `lib/scheduler/core/isolation.py` — `MountIsolation` + `CgroupLimits` | P1 |
| **23.2** | Intégrer mount namespace dans `DatasetProbeTask` (detection) | P1 |
| **23.3** | Intégrer cgroup limits dans executor (option par task) | P1 |
| **23.4** | Ajouter options isolation au security decorator DSL | P2 |

---

## ⏳ Restant complet

### P1

| ID | Description |
|----|-------------|
| **23.1-3** | Isolation cgroups/namespaces (voir ci-dessus) |
| **11.1** | SquashFS mount/overlay tasks |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **23.4** | Options isolation dans security decorator |
| **18.1-3** | Tests |