# Where every claim in this repository comes from

| Document | Status | Published | Verified against the publisher record on |
|---|---|---|---|
| UPnP Device Architecture 2.0, document revision 2020-04-17 | Current. Published by the Open Connectivity Foundation, which received the UPnP Forum's assets on 2016-01-01; versions 1.0 and 1.1 are archive. URL: https://openconnectivity.org/upnp-specs/UPnP-arch-DeviceArchitecture-v2.0-20200417.pdf. The PDF did not extract as text with the tools used, so **no UDA section number is verified**; cite the document only | 2020-04-17 | 2026-11-13 (OCF's UPnP page) |
| GENA (draft-cohen-gena-p-base 1998, draft-cohen-gena-client-00 1999-06-24) | Two expired Microsoft Internet-Drafts, never an RFC, not OASIS. History only: UPnP eventing is defined inside UDA 2.0 | 1998, 1999 | 2026-11-13 (secondary: IETF datatracker via search; not read) |
| SDDL 1.0 | **Unverified, removed.** Not listed on OCF's UPnP page (which lists UDA, the Vendor's Implementation Guide, a UUID draft and per-device and per-service DCPs). Restore only with a named source | - | 2026-11-13 |
| SSDP | Specified inside UDA 2.0. The only IETF material is an expired Internet-Draft (draft-cai-ssdp-v1), outside rfclib: a search of rfclib for SSDP, HTTPU and HTTPMU finds only passing mentions in RFC 6886 and others | - | 2026-11-13 |
| RFC 9110 | Internet Standard (STD 97) | 2022-06 | 2026-11-05 |
| RFC 9112 | Internet Standard (STD 99), current, obsoletes RFC 7230, updated by RFC 9931; 2 verified errata | 2022-06 | 2026-11-13 |
| RFC 9562 | Proposed Standard, current, obsoletes RFC 4122; 5 verified errata | 2024-05 | 2026-11-13 |
| Extensible Markup Language (XML) 1.0, Fifth Edition | W3C Recommendation, current | 2008-11-26 | 2026-11-13 (https://www.w3.org/TR/xml/) |

OCF still publishes the device control protocols (MediaServer, MediaRenderer, IGD and others); they stay a non-goal here, and the non-goal is dated 2026-11-13.

Citation rules, in the order they most often get broken:

1. Cite the document. A secondary write-up is a lead, not a source.
2. A section number is cited only if that section was read in full.
3. Errata are checked at each milestone freeze, not once at the start.
4. Where a claim came from a body outside the RFC series, that body is named here.

Re-verify with the RFC library rather than memory: `info('RFCnnnn')` for current status, `errata('RFCnnnn')` for corrections, and `read('RFCnnnn', view='normative')` for the MUST and SHOULD statements that become obligation rows.
