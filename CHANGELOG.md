# Changelog

The format follows Keep a Changelog, and this project adheres to Semantic Versioning.

## Unreleased

- `xmlsafe.parse(..., allow_external_id=True)` accepts a bare DOCTYPE with a `SYSTEM` or `PUBLIC` identifier and no
  internal subset; the identifier is never fetched and every entity, notation and internal subset is still refused.
- `devicespy/__init__` is lazy (PEP 562): `import devicespy.xmlsafe` no longer loads the UPnP modules.

Nothing yet. This repository is a shell: the public surface exists as typed stubs that raise
`NotImplementedError`, and [ROADMAP.md](ROADMAP.md) lists what has to happen first.

## 0.0.0 - 2026-11-05

### Added

- Package skeleton, obligation matrix and CI gates for devicespy.
- `devicespy.apps` namespace reserved for composition that is not protocol behaviour.
