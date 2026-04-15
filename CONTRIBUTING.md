# Contributing to fsdeploy

We welcome contributions! Here are a few guidelines.

## Development environment

1. Clone the repository:
   ```bash
   git clone https://github.com/your‑org/fsdeploy.git
   cd fsdeploy
   ```

2. Switch to the `dev` branch (the main development branch):
   ```bash
   git checkout dev
   ```

3. Install dependencies (see `README.md` for details).

## Contribution workflow

1. Create a feature branch from `dev`:
   ```bash
   git checkout -b feature/my‑feature
   ```

2. Make your changes, ensuring they follow the existing code style.

3. Test your changes (run the existing test suite with `pytest`).

4. Commit your changes with a descriptive message.

5. Push the branch and open a pull request against the `dev` branch.

## Directory structure

Key directories:

- `fsdeploy/lib/` – Core library (scheduler, configuration, UI, etc.)
- `fsdeploy/lib/ui/screens/` – Textual UI screens
- `fsdeploy/contrib/` – **Contributed scripts and integration files**

### The `contrib/` directory

The `fsdeploy/contrib/` folder contains ready‑to‑use integration files for various
init systems, service managers, and third‑party tools.

- `openrc/` – OpenRC init script (`fsdeploy.init`)
- `systemd/` – systemd service unit (`fsdeploy.service`)
- (Other sub‑directories may be added in the future)

These files are meant to be copied to the appropriate system directories
(e.g., `/etc/init.d/` for OpenRC, `/etc/systemd/system/` for systemd) after
adjusting any paths that may differ on the target system.

**Permissions**: Ensure that scripts have the correct execute permissions.
For OpenRC: `chmod +x fsdeploy.init`. For systemd: `chmod 644 fsdeploy.service`.

## Code style

- Use **Black** formatting for Python code (line length 88).
- Type hints are strongly encouraged for all function signatures.
- Use descriptive variable names and add docstrings for public functions/classes.

## Questions?

Feel free to open an issue on GitHub if you have any questions about the project.
