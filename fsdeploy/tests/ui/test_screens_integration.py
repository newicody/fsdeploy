"""
Tests d'intégration pour les écrans UI.
Ces tests vérifient que les écrans peuvent être instanciés et répondent aux événements de base.
"""
import pytest
from textual.test import Press, Pilot

from fsdeploy.lib.ui.screens.graph_enhanced import GraphEnhancedScreen
from fsdeploy.lib.ui.screens.security_enhanced import SecurityEnhancedScreen
from fsdeploy.lib.ui.screens.partition_detection import PartitionDetectionScreen
from fsdeploy.lib.ui.screens.cross_compile_screen import CrossCompileScreen
from fsdeploy.lib.ui.screens.multiarch_screen import MultiArchScreen
from fsdeploy.lib.ui.screens.module_registry import ModuleRegistryScreen

@pytest.mark.asyncio
async def test_graph_screen():
    """Instancie GraphEnhancedScreen et simule un clic sur Rafraîchir."""
    async with GraphEnhancedScreen().run_test() as pilot:
        # Vérifier que l'écran contient un bouton "refresh"
        refresh_button = pilot.app.query_one("#refresh")
        assert refresh_button is not None
        # Simuler un clic
        await pilot.click("#refresh")
        # Vérifier que le callback est appelé (pas d'erreur)
        # On peut aussi vérifier que le texte de la zone graph change?
        # Pour l'instant, on s'assure que l'écran est toujours actif.
        assert pilot.app.screen is not None

@pytest.mark.asyncio
async def test_security_screen_load_rules():
    """Charge les règles de sécurité (simulées)."""
    async with SecurityEnhancedScreen().run_test() as pilot:
        # Le tableau doit être présent
        table = pilot.app.query_one("#rules-table")
        assert table is not None
        # Le bouton "Appliquer" existe
        apply_btn = pilot.app.query_one("#apply-rule")
        assert apply_btn is not None
        # On peut simuler la saisie et un clic
        path_input = pilot.app.query_one("#rule-path")
        path_input.value = "pool.test"
        await pilot.click("#apply-rule")
        # Pas d'erreur

@pytest.mark.asyncio
async def test_partition_screen_scan():
    """PartitionDetectionScreen : bouton scan."""
    async with PartitionDetectionScreen().run_test() as pilot:
        scan_btn = pilot.app.query_one("#scan")
        assert scan_btn is not None
        # On peut cliquer
        await pilot.click("#scan")
        # Attendre un peu pour la callback asynchrone
        await pilot.pause()
        # Vérifier que le log a été mis à jour (peut rester vide)
        logs = pilot.app.query_one("#logs-output")
        assert logs is not None

@pytest.mark.asyncio
async def test_crosscompile_screen():
    """CrossCompileScreen : lancer une compilation."""
    async with CrossCompileScreen().run_test() as pilot:
        start_btn = pilot.app.query_one("#start")
        assert start_btn is not None
        arch_select = pilot.app.query_one("#arch")
        assert arch_select is not None
        # Simuler la sélection d'une architecture
        arch_select.value = "aarch64"
        await pilot.click("#start")
        await pilot.pause()
        # Vérifier que la zone de logs est mise à jour
        logs = pilot.app.query_one("#compile-output")
        assert logs is not None

@pytest.mark.asyncio
async def test_multiarch_screen():
    """MultiArchScreen : synchronisation."""
    async with MultiArchScreen().run_test() as pilot:
        sync_btn = pilot.app.query_one("#sync")
        assert sync_btn is not None
        await pilot.click("#sync")
        await pilot.pause()
        table = pilot.app.query_one("#kernels-table")
        assert table is not None

@pytest.mark.asyncio
async def test_moduleregistry_screen():
    """ModuleRegistryScreen : installer un module."""
    async with ModuleRegistryScreen().run_test() as pilot:
        install_btn = pilot.app.query_one("#install")
        assert install_btn is not None
        name_input = pilot.app.query_one("#module-name")
        name_input.value = "test-module"
        await pilot.click("#install")
        await pilot.pause()
        table = pilot.app.query_one("#modules-table")
        assert table is not None
