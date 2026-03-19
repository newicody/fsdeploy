"""
Security Resolver

Transforme les métadonnées des décorateurs en règles effectives.

Responsabilités :

- lire la config (configobj)
- matcher les paths (dataset.snapshot, etc.)
- fusionner config + options du décorateur
- produire :
    - ressources
    - locks
    - contraintes

C'est le lien entre :

DSL (decorator) → exécution réelle (scheduler)
"""
class SecurityResolver:

    def __init__(self, policies=None):
        self.policies = policies or []

    # -------------------------
    # ENTRY POINT
    # -------------------------
    def check(self, task, context):
        """
        Vérifie si la task est autorisée
        """

        # -------------------------
        # BASIC ROLE CHECK
        # -------------------------
        required_role = getattr(task, "required_role", None)
        user_role = context.get("role")

        if required_role and user_role != required_role:
            return False, f"Role '{user_role}' not allowed (requires '{required_role}')"

        # -------------------------
        # CUSTOM POLICIES
        # -------------------------
        for policy in self.policies:
            allowed, reason = policy(task, context)

            if not allowed:
                return False, reason

        return True, None
