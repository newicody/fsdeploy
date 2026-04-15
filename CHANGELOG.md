# Changelog

All notable changes to fsdeploy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-15

### Added
- Validation of `FsDeployConfig` in `ModuleRegistryScreen`.
- Access to `self.app.bridge` in all UI screens (`CrossCompileScreen`, `GraphScreen`, `IntentLogScreen`, `MultiArchScreen`, `SecurityScreen`, and newly created `ModuleRegistryScreen`).
- Documentation for `fsdeploy/contrib/` in `CONTRIBUTING.md`.
- Permissions fixes for init scripts (`chmod +x` for OpenRC, `chmod 644` for systemd).

### Changed
- Updated `PLAN.md` to reflect completion of steps 7.13‑7.18.
- Improved integration of configuration and bridge across the application.

### Fixed
- None.

## [0.9.0] - 2026-04-01

### Added
- Initial development branch `dev`.
- Basic scheduler, UI screens, and module system.
