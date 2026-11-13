# Where every claim in this repository comes from

| Document | Status | Published | Verified against the publisher record on |
|---|---|---|---|
| UPnP Device Architecture 2.0, document revision 2020-04-17 | Current. Published by the Open Connectivity Foundation, which received the UPnP Forum's assets on 2016-01-01; versions 1.0 and 1.1 are archive. URL: https://openconnectivity.org/upnp-specs/UPnP-arch-DeviceArchitecture-v2.0-20200417.pdf. The PDF extracts as text (`pdftotext`, 197 pages, sha256 9aa6eb29...f202); the clauses read on 2026-11-13 are listed in `docs/uda-outline.md` and cited by number | 2020-04-17 | 2026-11-13 (OCF's UPnP page) |
| GENA (draft-cohen-gena-p-base 1998, draft-cohen-gena-client-00 1999-06-24) | Two expired Microsoft Internet-Drafts, never an RFC, not OASIS. History only: UPnP eventing is defined inside UDA 2.0 | 1998, 1999 | 2026-11-13 (secondary: IETF datatracker via search; not read) |
| SDDL 1.0 | **Unverified, removed.** Not listed on OCF's UPnP page (which lists UDA, the Vendor's Implementation Guide, a UUID draft and per-device and per-service DCPs). Restore only with a named source | - | 2026-11-13 |
| SSDP | Specified inside UDA 2.0. The only IETF material is an expired Internet-Draft (draft-cai-ssdp-v1), outside rfclib: a search of rfclib for SSDP, HTTPU and HTTPMU finds only passing mentions in RFC 6886 and others | - | 2026-11-13 |
| RFC 9110 | Internet Standard (STD 97) | 2022-06 | 2026-11-05 |
| RFC 9112 | Internet Standard (STD 99), current, obsoletes RFC 7230, updated by RFC 9931; 2 verified errata | 2022-06 | 2026-11-13 |
| RFC 9562 | Proposed Standard, current, obsoletes RFC 4122; 5 verified errata | 2024-05 | 2026-11-13 |
| Extensible Markup Language (XML) 1.0, Fifth Edition | W3C Recommendation, current | 2008-11-26 | 2026-11-13 (https://www.w3.org/TR/xml/) |
| RFC 2616 | **OBSOLETE**, obsoleted by RFC 7230 to 7235 (so by RFC 9110, 9111, 9112); 7 verified errata; cited by UDA 2.0 for the DATE format | 1999-06 | 2026-11-13 |
| RFC 2141 | **OBSOLETE**, obsoleted by RFC 8141; cited by UDA 2.0 for vendor domain names in URNs | 1997-05 | 2026-11-13 |
| RFC 4340 | Proposed Standard, current, updated by RFC 5595, 5596, 6335, 6773; cited by UDA 2.0 only for the 49152 to 65535 port range | 2006-03 | 2026-11-13 |
| RFC 3986 | Internet Standard (STD 66), current, updated by RFC 7320, 8820; cited by UDA 2.0 for URLs | 2005-01 | 2026-11-13 |

OCF still publishes the device control protocols (MediaServer, MediaRenderer, IGD and others); they stay a non-goal here, and the non-goal is dated 2026-11-13.


Citation rules, in the order they most often get broken:

1. Cite the document. A secondary write-up is a lead, not a source.
2. A section number is cited only if that section was read in full.
3. Errata are checked at each milestone freeze, not once at the start.
4. Where a claim came from a body outside the RFC series, that body is named here.

Re-verify with the RFC library rather than memory: `info('RFCnnnn')` for current status, `errata('RFCnnnn')` for corrections, and `read('RFCnnnn', view='normative')` for the MUST and SHOULD statements that become obligation rows.
