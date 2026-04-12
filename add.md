# add.md — Action 5.1 : Tests unitaires par intent

**Date** : 2026-04-12

---

## État actuel

Seul `tests/test_intent.py` teste la classe de base `Intent`. Aucun test ne vérifie que les intents métier (`detection_intent`, `kernel_intent`, `system_intent`, `boot_intent`, `init_intent`) produisent les bonnes tasks via `build_tasks()`.

---

## Objectif

Créer `fsdeploy/tests/unit/test_intents_build.py` qui vérifie pour chaque intent enregistré que `build_tasks()` retourne une liste non-vide de `Task` avec les bons types.

Tests à écrire (~15) :
- `test_detection_start` → `DetectionTask`
- `test_pool_import_all` → `PoolImportAllTask`
- `test_kernel_list` → `KernelListTask`
- `test_kernel_provision` → `KernelProvisionTask`
- `test_coherence_check` → `CoherenceCheckTask`
- `test_preset_list` → `PresetListTask`
- `test_snapshot_create` → `SnapshotCreateTask`
- `test_stream_start` → `StreamStartTask`
- `test_health_check` → `HealthCheckTask`
- `test_init_detect` → `InitCheckTask`
- `test_zbm_install` → `ZBMInstallTask`
- `test_config_snapshot_save` → `ConfigSnapshotTask`
- `test_debug_exec` → `DebugExecTask`
- `test_mount_request` → `MountDatasetTask`
- `test_security_status` → `SecurityStatusTask`

Chaque test instancie l'intent avec des params minimaux et vérifie `len(build_tasks()) > 0` + `isinstance(tasks[0], expected_class)`.

---

## Fichier Aider

```
fsdeploy/tests/unit/test_intents_build.py
```

---

## Après

5.1 terminé. Prochaine : **5.2** (tests TUI textual pilot).
