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
| `events.notify()` | UDA 2.0 eventing | `[ ]` | `tests/test_obligations.py::test_notify` (to be written) | M4 |
| `events.renew()` | UDA 2.0 eventing | `[ ]` | `tests/test_obligations.py::test_renew` (to be written) | M4 |
| `xmlsafe.parse()` | design | `[ok]` | `tests/test_xmlsafe.py::test_refuses_doctype`, `tests/test_xmlsafe.py::test_refuses_internal_entity_declaration`, `tests/test_xmlsafe.py::test_depth_limit`, `tests/test_xmlsafe.py::test_huge_attribute_refused` | M1 |
| SSDP `byebye` on shutdown (`advertise.announce` with the byebye form) | UDA 2.0 | `[ ]` | (to be written) | M2 |
| SSDP boot id, config id and `NEXTBOOTID.UPNP.ORG` handling | UDA 2.0 | `[ ]` | (to be written) | M2 |
| max-age re-advertisement and the random delay up to MX on search responses | UDA 2.0 | `[ ]` | (to be written) | M2 |
| one LOCATION per interface for a multi-homed device | UDA 2.0 | `[ ]` | (to be written) | M2 |
| subscribe `CALLBACK` URL validation: a subscriber names a URL the device then connects to, so refuse non-LAN and non-HTTP targets (hostile-input row) | UDA 2.0 | `[ ]` | (to be written) | M4 |
| subscription table, NOTIFY delivery with timeouts and backoff, SEQ handling, expiry sweep | UDA 2.0 | `[ ]` | (to be written) | M4 |
| SOAP `UPnPError` faults and argument typing from the SCPD data types | UDA 2.0 | `[ ]` | (to be written) | M3 |
| `example.basic-device`: an independent stdlib control point over loopback fetches the description, invokes an action and receives an event | UDA 2.0 | `[ ]` | (to be written) | M5 |
| UDA 2.0 section outline, `docs/uda-outline.md`, with each normative sentence a row cites, read from the PDF and dated | UDA 2.0 | `[ ]` | (to be written) | M1 |
| spine repair: publisher, GENA, SDDL, RFC 9112 recorded in README and rfc-map; the projecthub generator data (`shells/data/naming.py`) still carries the old text; docs here are corrected | design | `[ ]` | (to be written) | M1 |
| `xmlsafe` XML 1.0 refusal rules for CDATA, `xml:` attributes and charset edge cases checked against the W3C text | XML 1.0 Fifth Edition | `[ ]` | (to be written) | M1 |

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

- UDA is outside the RFC series: pin `UDA 2.0 (2020-04-17)` in every docstring and cite no section until the PDF has been read.
- GENA was two expired Microsoft Internet-Drafts, never OASIS; eventing is defined inside UDA 2.0. "SDDL 1.0" was not found on the Open Connectivity Foundation's UPnP page and is removed.
- SSDP is specified by UDA 2.0; the only IETF material is an expired draft that rfclib does not hold.

## 4. Deliberate non-goals

| Non-goal | Status | Revisit when |
|---|---|---|
| a control point: use async-upnp-client, which is better at it than this will be | `[no]` | a named document requires it |
| DLNA or IGD semantics in the first release, only the generic device layer beneath them | `[no]` | a named document requires it |
| port mapping through an Internet Gateway Device, which is a profile, not the protocol | `[no]` | a named document requires it |

## 5. Open questions

- closed 2026-11-13: speak SSDP, HTTPU and HTTPMU directly, no dependency on `ssdp` (docs/strategy.md)
- M5 names a reference example device and control-point interop, but no api row sits on it: add a row, or drop the rung

## 6. Publication checklist

- [ ] every `[ ]` row above either `[ok]` or moved to a named later milestone
- [ ] `docs/research.md` claims re-verified and the dated ones either promoted or deleted
- [ ] interoperability evidence recorded in `docs/` against a non-Python implementation
- [ ] `tools/check_dist.py` proves the wheel ships the fixtures the README promises
- [ ] version 0.1.0 tagged, trusted publisher configured, README badges uncommented
