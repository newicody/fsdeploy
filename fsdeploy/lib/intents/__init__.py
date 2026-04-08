"""
fsdeploy.intents
=================
Tous les Intents du systeme.

L'import de ce package declenche l'enregistrement de tous les
@register_intent dans le INTENT_REGISTRY global.
"""

# Les imports ci-dessous enregistrent les handlers dans le registry.
# Ils sont aussi importes explicitement par daemon._register_all_intents().

try:
    from intents.boot_intent import *
except ImportError:
    pass

try:
    from intents.detection_intent import *
except ImportError:
    pass

try:
    from intents.kernel_intent import *
except ImportError:
    pass

try:
    from intents.system_intent import *
except ImportError:
    pass

try:
    from intents.test_intent import *
except ImportError:
    pass

try:
    from intents.config_intent import *
except ImportError:
    pass

try:
    from intents.integration_intent import *
except ImportError:
    pass

try:
    from intents.kernel_module_intent import *
except ImportError:
    pass

try:
    from intents.init_config_intent import *
except ImportError:
    pass
