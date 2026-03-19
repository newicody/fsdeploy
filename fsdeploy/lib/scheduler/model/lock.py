"""
Lock model

Un lock est appliqué sur une ressource pour éviter les conflits.

Exemple :

- empêcher deux opérations sur le même dataset
- empêcher un destroy pendant un snapshot

Chaque lock est associé à un intent.
"""

class Lock:

    def __init__(self, resource):
        self.resource = resource

    def conflicts(self, other):
        return self.resource.conflicts(other.resource)

    def __repr__(self):
        return f"<Lock {self.resource}>"

    def get_resource(self):
        """
        Retourne la ressource verrouillée.
        """
        pass


    def get_owner(self):
        """
        Retourne l'ID de l'intent propriétaire.
        """
        pass
