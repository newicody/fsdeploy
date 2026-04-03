"""
fsdeploy.ui.compat
====================
Couche de compatibilite Textual 0.x → 8.x.

Textual 8.x changements :
  - DataTable n'emet *Selected qu'au 2eme clic
  - Select.BLANK → Select.NULL
  - OptionList Separator → None
  - query_one breadth-first (pas d'impact si IDs uniques)

Usage dans les ecrans :
  from ui.compat import SELECT_BLANK, DATATABLE_USE_HIGHLIGHTED

  # Au lieu de on_data_table_row_selected, utiliser :
  def on_data_table_row_highlighted(self, event):
      ...

  # Au lieu de Select.BLANK, utiliser :
  if my_select.value != SELECT_BLANK:
      ...
"""

from textual.widgets import Select

# Select.BLANK renomme Select.NULL dans Textual 8.x
# On supporte les deux noms pour compatibilite
SELECT_BLANK = getattr(Select, "NULL", getattr(Select, "BLANK", None))

# Indique que les ecrans doivent utiliser RowHighlighted au lieu de RowSelected
# pour la selection au premier clic (Textual 8.x change le comportement)
DATATABLE_USE_HIGHLIGHTED = True

# Version minimale Textual supportee
TEXTUAL_MIN_VERSION = "8.2.1"


def check_textual_version() -> tuple[bool, str]:
    """Verifie que la version de Textual est compatible."""
    try:
        import textual
        version = textual.__version__
        major = int(version.split(".")[0])
        if major < 8:
            return False, f"Textual {version} < 8.x — migration necessaire"
        return True, f"Textual {version} OK"
    except (ImportError, ValueError):
        return False, "Textual non installe"


def check_rich_version() -> tuple[bool, str]:
    """Verifie que la version de Rich est compatible."""
    try:
        import rich
        version = rich.__version__
        parts = version.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        if major < 14 or (major == 14 and minor < 2):
            return False, f"Rich {version} < 14.2.0 — Textual 8.x exige >=14.2.0"
        return True, f"Rich {version} OK"
    except (ImportError, ValueError):
        return False, "Rich non installe"
