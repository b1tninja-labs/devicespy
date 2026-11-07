# Specification completeness -- and the roadmap it implies

This is the project's north star: every protocol obligation devicespy could plausibly take on,
with an honest status against the code at `HEAD`. It is blunt about gaps on purpose. A
roadmap that overstates its coverage is not a plan, it is marketing.

**The honesty rule:** a row may read `[ok]` only when a named test would fail if the
behaviour regressed. Reading the code and agreeing with it is not enough. That is how
"decoded but never sent" quietly becomes "implemented".

Legend: `[ok]` implemented and pinned by a named test -- `[part]` partial, with what is
missing stated -- `[ ]` not implemented -- `[no]` deliberate non-goal.

A Where cell marked `(to be written)` names the test that will pin the row once it exists; no
such test has been written yet, and the row cannot leave `[ ]` until it has. The Milestone
column places the row on the ladder in section 2, and `-` means it is not placed yet.

Update the affected row in the same commit that changes the behaviour. A row and its test
drift apart within one release, and the document becomes useless exactly when it is needed.

## 1. Obligations

| Obligation | Spec | Status | Where | Milestone |
|---|---|---|---|---|
| `advertise.announce()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_announce` (to be written) | M2 |
| `advertise.search_response()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_search_response` (to be written) | M2 |
| `description.render_device_xml()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_render_device_xml` (to be written) | M1 |
| `scpd.parse_scpd()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_parse_scpd` (to be written) | M1 |
| `control.dispatch()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_dispatch` (to be written) | M3 |
| `events.notify()` | GENA 1.0 | `[ ]` | `tests/test_obligations.py::test_notify` (to be written) | M4 |
| `events.renew()` | GENA 1.0 | `[ ]` | `tests/test_obligations.py::test_renew` (to be written) | M4 |
| `xmlsafe.parse()` | design | `[ ]` | `tests/test_obligations.py::test_parse` (to be written) | M1 |

## 2. Milestones

- M1 hardened XML parser plus description and SCPD round trip
- M2 SSDP advertisement and search responses on Windows and Linux multicast
- M3 control dispatch with typed arguments and error codes
- M4 GENA subscriptions, renewals and evented properties
- M5 a reference example device, then interop testing against a real control point
- M6 publication: 0.1.0

Every milestone is accepted by its rows above flipping to `[ok]` with a named test, not by
the code existing. Coverage in `pyproject.toml` ratchets in the same commit.

## 3. Errata watch

- UDA and GENA are outside the RFC series: pin the exact specification revision in every docstring.
- SSDP itself has a maintained Python owner already (ssdp 1.3.1), so the design decision is whether to depend on it or speak multicast HTTP directly. Record the reasoning in docs/strategy.md before writing code.

## 4. Deliberate non-goals

| Non-goal | Status | Revisit when |
|---|---|---|
| a control point: use async-upnp-client, which is better at it than this will be | `[no]` | a named document requires it |
| DLNA or IGD semantics in the first release, only the generic device layer beneath them | `[no]` | a named document requires it |
| port mapping through an Internet Gateway Device, which is a profile, not the protocol | `[no]` | a named document requires it |

## 5. Open questions

- depend on the maintained ssdp library or speak multicast HTTP directly
- M5 names a reference example device and control-point interop, but no api row sits on it: add a row, or drop the rung

## 6. Publication checklist

- [ ] every `[ ]` row above either `[ok]` or moved to a named later milestone
- [ ] `docs/research.md` claims re-verified and the dated ones either promoted or deleted
- [ ] interoperability evidence recorded in `docs/` against a non-Python implementation
- [ ] `tools/check_dist.py` proves the wheel ships the fixtures the README promises
- [ ] version 0.1.0 tagged, trusted publisher configured, README badges uncommented
