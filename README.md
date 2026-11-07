# devicespy

<!-- PyPI badges go live with the first release. Until then a version badge renders
     "no version" on the landing page, which reads as a defect rather than a date, so
     the badges stay commented out until the tag exists.
-->

**Pre-alpha shell.** The package surface, the obligation matrix and the CI gates exist.
No protocol behaviour is implemented: every public function raises `NotImplementedError`,
and the test suite records that rather than hiding it. Read
[ROADMAP.md](ROADMAP.md) before depending on any of it.

devicespy -- be the UPnP device, not the control point

Every Python UPnP library is a control point. async-upnp-client 0.49.0 (2026-10-11), upnpclient 2.0.3 (2026-04-07) and python-upnp 1.0.0 (2024-07-12) all talk to devices, and ssdp 1.3.1 (2025-09-06) plus ssdpy 0.4.1 do discovery. Nothing lets a Python program be a device: advertise itself, publish its description and SCPD, answer control requests and push events. That is the half a printer, scanner or media server needs, and it is also the security-sensitive half, because a device parses XML that a stranger on the LAN wrote.

## The gap, with a date

PyPI was queried on 2026-11-05 for this name and for every neighbouring project. Landscape
claims rot quickly: two projects in this portfolio shipped within five days of the survey,
which is why the table below carries dates instead of adjectives.

| Project | Version | Last release | Why it is not this project |
|---|---|---|---|
| async-upnp-client | 0.49.0 | 2026-10-11 | the reference control point; it is not a device stack |
| upnpclient | 2.0.3 | 2026-04-07 | client only, revived |
| ssdp, ssdpy | 1.3.1, 0.4.1 | 2025-09-06 | discovery transport, already solved |
| upnp-device, upnp-server, deviceupnp | - | - | all absent from PyPI (2026-11-05) |

What this project intends to add:

- advertise and live lifecycle: alive, byebye, search response, and bootId changes on restart
- description and SCPD authoring with validation, so a malformed service does not ship
- SOAP control dispatch with argument typing and action-level authorisation
- GENA subscription manager: renewals, evented properties, seqnum, and resubscribe on loss
- defensive XML: no DTDs, no external entities, bounded size, since the peer is a stranger

## Specification spine

Status and publication dates below were read from the RFC Editor record on 2026-11-05. A
section number is cited only where that section was read in full; everything else cites the
document, which is the honest grain size for a plan. See [docs/rfc-map.md](docs/rfc-map.md).

| Document | Status | Published | What it gives this project |
|---|---|---|---|
| UDA 2.0 (UPnP Device Architecture) | UPnP Forum | - | device and service description, control, eventing, boot sequence |
| GENA 1.0 | OASIS | - | subscribe, renew, notify, unsubscribe |
| SDDL 1.0 | UPnP Forum | - | device and service description discovery layout |
| RFC 9110 | Internet Standard (STD 97) | 2022-06 | the HTTP semantics every UPnP exchange rides on |

### Errata watch

- UDA and GENA are outside the RFC series: pin the exact specification revision in every docstring.
- SSDP itself has a maintained Python owner already (ssdp 1.3.1), so the design decision is whether to depend on it or speak multicast HTTP directly. Record the reasoning in docs/strategy.md before writing code.

## Module layout

| Module | Responsibility |
|---|---|
| `advertise` | SSDP alive, byebye and search responses (UDA 2.0, SDDL 1.0) |
| `description` | device and service description documents (UDA 2.0) |
| `scpd` | service control protocol definition: actions, state variables, allowed values |
| `control` | SOAP action dispatch with argument coercion (UDA 2.0) |
| `events` | GENA subscriptions and evented property change notifications (GENA 1.0) |
| `xmlsafe` | the hardened parser every other module must use |
| `httpd` | the small asyncio HTTP surface the device serves (RFC 9110) |

## What it does not do

- a control point: use async-upnp-client, which is better at it than this will be
- DLNA or IGD semantics in the first release, only the generic device layer beneath them
- port mapping through an Internet Gateway Device, which is a profile, not the protocol


## Install

```bash
git clone https://github.com/b1tninja/devicespy.git
cd devicespy
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
```

Not published to PyPI yet. The name is reserved for this repository's trusted publisher at
the moment of the first release.

## Development

All four gates must pass, on Linux and Windows alike:

```bash
ruff check . && ruff format --check .
mypy devicespy tests
pytest -q --cov
python -O -m pytest -q
```

The last line is the one that matters most in a protocol library. `-O` strips `assert`, and a
parser whose bounds checks were asserts stops being a parser under production flags. Wire
paths raise named exceptions; asserts belong in tests and nowhere else.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
