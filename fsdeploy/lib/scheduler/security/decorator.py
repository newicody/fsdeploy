"""
Security Decorator

Permet de lier les classes (tasks) à une hiérarchie de configuration.

Exemples :

@security.dataset.snapshot
@security.dataset.create(entire=True)

Le décorateur ne contient PAS la logique de sécurité.
Il expose uniquement :

- un chemin hiérarchique (path)
- des options locales

Le scheduler combinera ensuite :

decorator metadata + config → règles effectives
"""

class SecurityDecorator:
    """
    Point d'entrée du décorateur.
    """

    def __getattr__(self, name):
        """
        Permet de construire dynamiquement la hiérarchie.
        """
        pass


    def __call__(self, **options):
        """
        Permet l'utilisation directe :
        @security(...)
        """
        pass

class SecurityNode:
    """
    Représente un nœud dans la hiérarchie du décorateur.
    """

    def __init__(self, path):

        # chemin hiérarchique (liste)
        self.path = path


    def __getattr__(self, name):
        """
        Permet d'étendre le chemin :
        dataset → snapshot → create
        """
        pass


    def __call__(self, **options):
        """
        Applique le décorateur à une classe.
        """
        pass


