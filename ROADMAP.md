# Specification completeness -- and the roadmap it implies

This is the project's north star: every protocol obligation devicespy could plausibly take on,
with an honest status against the code at `HEAD`. It is blunt about gaps on purpose. A
roadmap that overstates its coverage is not a plan, it is marketing.

**The honesty rule:** a row may read `[ok]` only when a named test would fail if the
behaviour regressed. Reading the code and agreeing with it is not enough. That is how
"decoded but never sent" quietly becomes "implemented".

Legend: `[ok]` implemented and pinned by a named test -- `[part]` partial, with what is
missing stated -- `[ ]` not implemented -- `[no]` deliberate non-goal.

Update the affected row in the same commit that changes the behaviour. A row and its test
drift apart within one release, and the document becomes useless exactly when it is needed.

## 1. Obligations

| Obligation | Spec | Status | Where |
|---|---|---|---|
| `advertise.announce()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::announce` |
| `advertise.search_response()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::search_response` |
| `description.render_device_xml()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::render_device_xml` |
| `scpd.parse_scpd()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::parse_scpd` |
| `control.dispatch()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::dispatch` |
| `events.notify()` | GENA 1.0 | `[ ]` | `tests/test_obligations.py::notify` |
| `events.renew()` | GENA 1.0 | `[ ]` | `tests/test_obligations.py::renew` |
| `xmlsafe.parse()` | design | `[ ]` | `tests/test_obligations.py::parse` |

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

## 6. Publication checklist

- [ ] every `[ ]` row above either `[ok]` or moved to a named later milestone
- [ ] `docs/research.md` claims re-verified and the dated ones either promoted or deleted
- [ ] interoperability evidence recorded in `docs/` against a non-Python implementation
- [ ] `tools/check_dist.py` proves the wheel ships the fixtures the README promises
- [ ] version 0.1.0 tagged, trusted publisher configured, README badges uncommented
