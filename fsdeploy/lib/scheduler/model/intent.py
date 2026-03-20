"""
fsdeploy.scheduler.model.intent
================================
Intent = intention d'exécution dans le scheduler.

Un Intent produit une liste de Tasks via build_tasks().
Le Scheduler résout les Tasks (sécurité, ressources) puis les exécute.
"""

from typing import Any, Optional


class IntentID:
    """
    Identifiant hiérarchique.
    Racine : "1", enfants : "1.1", "1.2", petits-enfants : "1.1.1", etc.
    """

    __slots__ = ("value", "_child_counter")

    def __init__(self, value: str | int = "0"):
        self.value = str(value)
        self._child_counter = 0

    def next_child(self) -> "IntentID":
        self._child_counter += 1
        return IntentID(f"{self.value}.{self._child_counter}")

    def get(self) -> str:
        return self.value

    @property
    def depth(self) -> int:
        return self.value.count(".") + 1

    @property
    def parent_value(self) -> str | None:
        if "." not in self.value:
            return None
        return self.value.rsplit(".", 1)[0]

    def __repr__(self) -> str:
        return f"IntentID({self.value!r})"

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other) -> bool:
        if isinstance(other, IntentID):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


class Intent:
    """
    Intention d'exécution.

    Sous-classes : implémenter build_tasks() → list[Task].
    """

    def __init__(self, id: str | IntentID | None = None,
                 params: dict | None = None,
                 context: dict | None = None):
        if isinstance(id, IntentID):
            self.id = id
        else:
            self.id = IntentID(id or "0")

        self.params = params or {}
        self.context = context or {}
        self.status = "pending"  # pending | running | completed | failed
        self.parent: Optional["Intent"] = None
        self.children: list["Intent"] = []
        self.error: Optional[Exception] = None

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> bool:
        """Valide les pré-conditions. Override dans les sous-classes."""
        return True

    # ── Résolution ────────────────────────────────────────────────────────────

    def resolve(self) -> list:
        """
        Transforme l'intent en liste de tasks enrichies.
        Appelle build_tasks() puis ajoute les IDs hiérarchiques et le contexte.
        """
        tasks = self.build_tasks()

        if tasks is None:
            return []
        if not isinstance(tasks, list):
            raise ValueError(f"{self.__class__.__name__}.build_tasks() must return a list")

        for i, task in enumerate(tasks):
            child_id = self.id.next_child()

            if hasattr(task, "id"):
                task.id = child_id.get()
            if hasattr(task, "context"):
                task.context = self.context
            if not hasattr(task, "meta"):
                task.meta = {}
            task.meta.update({
                "intent_id": self.id.get(),
                "intent_class": self.__class__.__name__,
                "step_index": i,
            })

        return tasks

    def build_tasks(self) -> list:
        """
        Produit la liste de Tasks. À implémenter dans les sous-classes.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement build_tasks()"
        )

    # ── Hiérarchie ────────────────────────────────────────────────────────────

    def add_child(self, intent: "Intent") -> None:
        intent.parent = self
        self.children.append(intent)

    def create_child(self, intent_cls, **kwargs) -> "Intent":
        """Crée un intent enfant avec un ID hiérarchique."""
        child_id = self.id.next_child()
        child = intent_cls(id=child_id, **kwargs)
        self.add_child(child)
        return child

    # ── Status ────────────────────────────────────────────────────────────────

    def set_status(self, status: str) -> None:
        self.status = status

    def mark_failed(self, error: Exception) -> None:
        self.status = "failed"
        self.error = error

    # ── Getters ───────────────────────────────────────────────────────────────

    def get_id(self) -> str:
        return self.id.get()

    def get_event(self):
        return self.context.get("event")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} status={self.status}>"
