Plan de développement fsdeploy — État réel

Dernière mise à jour : 2026-04-09 Branche cible : dev
Diagnostic global

Le PLAN.md précédent marquait tout comme "(terminé)". L'analyse croisée du code source, des sessions de debug et de l'architecture réelle révèle que l'infrastructure existe mais que beaucoup de composants ne sont pas fonctionnels en production. Le projet est en phase alpha avancée, pas production-ready.
Problèmes structurels identifiés

    Écrans TUI majoritairement squelettiques — les 11 écrans existent mais la plupart affichent des données statiques ou fictives, sans connexion réelle au scheduler via bridge.emit() → poll().
    Tests insuffisants — test_run.py contient 3 tests basiques. La suite test_all.py (30 tests) n'est pas finalisée. Aucun test d'intégration réel sur ZFS.
    Intégration init/ non faite — les scripts shell dans init/ ne sont pas portés dans lib/function/ selon le mapping convenu.
    GraphViewScreen déconnecté — pas câblé aux données live via get_state_snapshot().
    Logs disque absents — setup_logging() n'a pas de FileHandler, les logs ne survivent pas aux redémarrages.
    fsdeploy-web inexistant — le wrapper textual serve n'est pas créé.
    Cross-compilation non câblée — crosscompile.py couvre 25+ architectures en théorie, jamais testé.
    Classe de bugs silencieux — _handlers dict mal structuré, __pycache__ stale, mauvais thread pour signaux — ces bugs ont été corrigés sur main mais doivent être vérifiés sur dev.

[Fait] — Réellement fonctionnel et vérifié

    Architecture event→intent→task : pipeline complet, bridge.emit() → scheduler → intent → task → bridge.poll() via _bridge_ticket.
    Daemon (daemon.py) : instancie store + runtime + executor + scheduler + bus, _register_all_intents() avec factory closures, executor.shutdown(wait=True).
    Config (config.py + fsdeploy.configspec) : 19 sections, configobj, _secure_config_file chmod 640.
    Codec (codec.py) : HuffmanStore, 6 RecordStores, ~18× compression.
    Runtime (runtime.py) : thread-safe, threading.Lock sur toutes les mutations.
    Executor (executor.py) : ThreadPoolExecutor, callbacks non-bloquants, locks.
    Bridge (bridge.py) : émetteur pur, ticket tracking.
    Log (log.py) : structlog + ASCII fallback pour TERM=linux.
    CLI (__main__.py) : typer, 4 sous-commandes (detect, snapshot, coherence, status).
    launch.sh : bootstrap complet, DKMS wait, sudoers, venv, clone.
    Migration Textual 8.2.1 : Select.NULL, on_data_table_row_highlighted, compat.py.
    Bugfixes critiques : factory closures dans _register_all_intents(), SocketSource fallback, TUI main thread / scheduler daemon thread, Screen.name read-only, PoolImportAllTask import individuel, _on_mount renommé, PYTHONIOENCODING=utf-8, ASCII-only .py.

[En cours]

    Vérification branche dev : s'assurer que tous les bugfixes de main sont portés sur dev.
    Câblage écrans TUI : connecter chaque écran au scheduler via bridge.emit() / poll() au lieu de données fictives.

[À faire] — Par priorité
P0 — Bloquants pour un premier boot réel

    Porter les bugfixes main → dev : vérifier que _register_all_intents() utilise factory closures, SocketSource fallback, threading correct, etc.
    Câbler DetectionScreen : doit appeler bridge.emit("detection.start") et afficher les résultats réels de PoolImportAllTask + DatasetProbeTask.
    Câbler MountsScreen : propositions de montage réelles basées sur la détection, validation utilisateur, mount -t zfs.
    Câbler KernelScreen : lister les noyaux trouvés, permettre sélection, symlinks, compilation optionnelle.
    Câbler InitramfsScreen : choix zbm/minimal/stream, génération réelle d'initramfs.
    Câbler CoherenceScreen : vérifications réelles (pools, datasets, montages, services, cmdline noyau).
    Câbler SnapshotsScreen : CRUD snapshots ZFS réel.
    Câbler ZBMScreen : installation/configuration ZFSBootMenu réelle.

P1 — Fonctionnalités manquantes critiques

    Intégration init/ → lib/function/ :
        live_setup → lib/function/live/setup.py
        init_script → lib/function/boot/init.py
        switch → enrichit lib/function/rootfs/switch.py
        network → lib/function/network/setup.py
        initramfs_hook → lib/function/boot/initramfs.py
        entry → lib/intents/boot_intent.py
        environment → lib/function/detect/environment.py
        services → lib/function/service/
        bus → Event sources pour EventQueue
    FileHandler dans setup_logging() : logs persistants sur disque.
    Wrapper fsdeploy-web : textual serve via textual-dev.
    Tests : compléter test_all.py (30 tests couvrant toutes les couches).

P2 — Améliorations

    GraphViewScreen live : câbler à get_state_snapshot() / get_scheduler_state().
    StreamScreen : configuration YouTube, lancement ffmpeg RTMP réel.
    ConfigScreen : éditeur fsdeploy.conf fonctionnel dans la TUI.
    DebugScreen : affichage logs/tasks/state en temps réel.
    PresetsScreen : CRUD presets JSON, sélection au boot.
    Cross-compilation : câbler crosscompile.py, tests sur au moins aarch64.
    Purge CLEANUP.md : supprimer ARCHITECTURE.py, huffman.py stub, core/intent.py duplicate, bus/init.py duplicate.
    NetworkScreen : configuration réseau, DHCP/static, streaming sans rootfs.

P3 — Polish

    Documentation utilisateur : compléter manuel.md.
    CI/CD : GitHub Actions pour lint + tests.
    Presets stream : boot sans rootfs, réseau + Python + ffmpeg uniquement.
    Hot-swap : switch noyau/modules/rootfs à chaud depuis la TUI post-boot.

Fichiers à modifier (prochaine itération)

Les fichiers suivants nécessitent des modifications pour atteindre P0 :
Fichier	Action
lib/ui/screens/detection.py	Câbler bridge.emit("detection.start"), afficher résultats réels
lib/ui/screens/mounts.py	Propositions montage depuis détection, validation, exécution
lib/ui/screens/kernel.py	Lister noyaux détectés, sélection, symlinks
lib/ui/screens/initramfs.py	Choix type, génération réelle
lib/ui/screens/coherence.py	Vérifications réelles ZFS
lib/ui/screens/snapshots.py	CRUD snapshots ZFS
lib/ui/screens/zbm.py	Installation ZFSBootMenu
lib/ui/screens/stream.py	Config YouTube + ffmpeg
lib/ui/screens/config.py	Éditeur fsdeploy.conf
lib/ui/screens/debug.py	Logs/tasks/state temps réel
lib/ui/screens/graph.py	Données live scheduler
lib/ui/app.py	Vérifier bridge.poll() cycle, intégration tous écrans
lib/daemon.py	Vérifier bugfixes portés de main
lib/log.py	Ajouter FileHandler
lib/intents/detection_intent.py	Vérifier factory closures
lib/intents/kernel_intent.py	Idem
lib/intents/system_intent.py	Idem
Principes rappelés

    Jamais de build parallèle : tout passe par l'architecture existante event→intent→task.
    Écrans TUI = zéro import de lib/ : tout via bridge.emit() / bridge.poll().
    mount -t zfs : forme canonique (pas zfs mount).
    Factory closures : obligatoires pour les callbacks dans les boucles.
    Purger __pycache__ : après tout remplacement de fichier.
    Fichiers complets : toujours livrer des fichiers entiers, jamais des patches.
    configobj : pas pydantic/dataclasses pour la config.
    Trois contextes : Debian Live / initramfs / système booté — même code, paramètre = mountpoint.
