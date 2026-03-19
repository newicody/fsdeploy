"""
Resource model

Une ressource représente un élément du système utilisé par une tâche.

Exemples :

- dataset:tank/home
- pool:tank
- device:nvme0
- kernel
- rootfs

Les ressources sont utilisées pour :

- gérer les conflits
- appliquer des locks
- contrôler le parallélisme
"""

class Resource:

    def __init__(self, path):
        if isinstance(path, str):
            self.path = tuple(path.split("."))
        else:
            self.path = tuple(path)

    def is_parent_of(self, other):
        if len(self.path) > len(other.path):
            return False
        return self.path == other.path[:len(self.path)]

    def conflicts(self, other):
        return self.is_parent_of(other) or other.is_parent_of(self)

    def __repr__(self):
        return ".".join(self.path)

    def get_id(self):
        """
        Retourne un identifiant unique de la ressource.
        ex : dataset:tank/home
        """
        pass


    def get_type(self):
        """
        Retourne le type de la ressource.
        """
        pass


    def get_name(self):
        """
        Retourne le nom de la ressource.
        """
        pass

