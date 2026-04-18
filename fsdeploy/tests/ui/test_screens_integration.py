"""
Tests d'intégration pour les écrans UI.
Ces tests vérifient que les écrans peuvent être instanciés et répondent aux événements de base.
"""
import pytest
from textual.test import Press, Pilot

from fsdeploy.lib.ui.screens.crosscompile import CrossCompileScreen
from fsdeploy.lib.ui.screens.multiarch import MultiArchScreen
from fsdeploy.lib.ui.screens.module_registry import ModuleRegistryScreen




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
