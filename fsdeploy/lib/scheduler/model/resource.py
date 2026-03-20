"""
fsdeploy.scheduler.model.resource
=================================
Ressource du système utilisée par une tâche.

Exemples : dataset.tank.home, pool.tank, device.nvme0, kernel, rootfs, efi.

Les ressources forment une hiérarchie : pool.tank est parent de pool.tank.dataset.home.
Deux ressources sont en conflit si l'une est parent de l'autre.
"""


class Resource:
    """
    Ressource hiérarchique identifiée par un chemin en points.

    Exemples :
        Resource("pool.tank")
        Resource("dataset.tank.home")
        Resource("kernel.6.12.0")
    """

    __slots__ = ("path",)

    def __init__(self, path):
        if isinstance(path, str):
            self.path = tuple(path.split("."))
        elif isinstance(path, (list, tuple)):
            self.path = tuple(path)
        else:
            raise TypeError(f"Resource path must be str, list or tuple, got {type(path)}")

    @property
    def resource_type(self) -> str:
        """Premier segment du chemin (pool, dataset, kernel, etc.)."""
        return self.path[0] if self.path else ""

    @property
    def name(self) -> str:
        """Chemin complet en notation pointée."""
        return ".".join(self.path)

    @property
    def id(self) -> str:
        """Alias de name pour compatibilité."""
        return self.name

    def is_parent_of(self, other: "Resource") -> bool:
        """Vrai si self est un ancêtre (ou égal) de other."""
        if len(self.path) > len(other.path):
            return False
        return self.path == other.path[: len(self.path)]

    def conflicts(self, other: "Resource") -> bool:
        """Vrai si les deux ressources partagent une relation parent-enfant."""
        return self.is_parent_of(other) or other.is_parent_of(self)

    def child(self, segment: str) -> "Resource":
        """Crée une sous-ressource."""
        return Resource(list(self.path) + [segment])

    def __eq__(self, other) -> bool:
        if isinstance(other, Resource):
            return self.path == other.path
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.path)

    def __repr__(self) -> str:
        return f"Resource({self.name!r})"

    def __str__(self) -> str:
        return self.name


# ─── Ressources pré-définies ─────────────────────────────────────────────────

KERNEL = Resource("kernel")
ROOTFS = Resource("rootfs")
EFI = Resource("efi")
INITRAMFS = Resource("initramfs")
NETWORK = Resource("network")
STREAM = Resource("stream")


def pool_resource(pool_name: str) -> Resource:
    return Resource(f"pool.{pool_name}")


def dataset_resource(dataset_name: str) -> Resource:
    return Resource(f"dataset.{dataset_name.replace('/', '.')}")


def device_resource(device: str) -> Resource:
    return Resource(f"device.{device}")
