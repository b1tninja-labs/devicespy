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
| `advertise.search_response()` writes the unicast 200 OK for each advertisement matching an ST (`ssdp:all`, `upnp:rootdevice`, `uuid:`, a type URN answered with the requested version) with CACHE-CONTROL, DATE, an empty EXT, LOCATION, SERVER, ST, USN and the boot, config and search-port fields; `parse_search_request` reads and refuses hostile M-SEARCH datagrams | UDA 2.0 clauses 1.3.2, 1.3.3 | `[ok]` | `tests/test_advertise.py::test_search_response_message`; `tests/test_advertise.py::test_search_targets`; `tests/test_advertise.py::test_a_lower_version_is_answered_with_the_requested_version`; `tests/test_advertise.py::test_malformed_search_requests_are_refused` | M2 |
| `description.render_device_xml()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_render_device_xml` (to be written) | M1 |
| `scpd.parse_scpd()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_parse_scpd` (to be written) | M1 |
| `control.dispatch()` | UDA 2.0 | `[ ]` | `tests/test_obligations.py::test_dispatch` (to be written) | M3 |
| `events.notify()` | UDA 2.0 eventing | `[ ]` | `tests/test_obligations.py::test_notify` (to be written) | M4 |
| `events.renew()` reassigns a duration within the minimum and maximum; `SubscriptionTable.renew` and `cancel` answer 400 and 412 per Tables 4-5 and 4-6 | UDA 2.0 eventing clauses 4.1.3, 4.1.4 | `[ok]` | `tests/test_events.py::test_module_renew_reassigns_a_duration`; `tests/test_events.py::test_renewal_and_cancellation_follow_tables_4_5_and_4_6` | M4 |
| `xmlsafe.parse()` | design | `[ok]` | `tests/test_xmlsafe.py::test_refuses_doctype`, `tests/test_xmlsafe.py::test_refuses_internal_entity_declaration`, `tests/test_xmlsafe.py::test_depth_limit`, `tests/test_xmlsafe.py::test_huge_attribute_refused` | M1 |
| `xmlsafe` sha256 pin list (`PINNED_DTD_FILES`, decided in PORTFOLIO section 9 item 15): refusal of every DTD stays the default; a document whose exact bytes hash to a pinned entry (`tr-106-types.xml` first: 21,157 bytes, sha256 68237466...84a1, from the Broadband Forum's data-model site, read 2026-11-13) may declare internal general entities only: no external identifier on the document type, no parameter entity, no external or unparsed entity, no notation, no element or attribute-list declaration, at most 64 entities of at most 1024 characters with no reference to another entity, and expanded text held to four times the size limit. A billion-laughs variant, a character-reference nesting variant, external and parameter entities are refused on pinned and unpinned files alike | design (PORTFOLIO section 9 item 15) | `[ok]` | `tests/test_xmlsafe.py::test_pinned_file_may_declare_internal_general_entities`; `tests/test_xmlsafe.py::test_the_same_file_is_refused_when_it_is_not_pinned`; `tests/test_xmlsafe.py::test_one_changed_byte_unpins_a_file`; `tests/test_xmlsafe.py::test_hostile_dtds_are_refused_unpinned`; `tests/test_xmlsafe.py::test_hostile_dtds_are_refused_even_when_pinned`; `tests/test_xmlsafe.py::test_expanded_text_is_bounded_for_a_pinned_file` | M1 |
| `xmlsafe` pin list against the real file: `tr-106-types.xml` parses and its entities expand into the patterns TR-181 uses; the test skips loudly when the cache (`$CWMP_DATA_CACHE`, filled by `../cwmp/tools/fetch_bbf.py`) is absent. The attribute-list refusal means a future pinned file with `<!ATTLIST>` needs a deliberate widening | design | `[ok]` | `tests/test_xmlsafe.py::test_the_real_tr_106_types_parses_when_the_cache_has_it` | M1 |
| SSDP `byebye` messages: one per alive row, HOST NT NTS USN BOOTID CONFIGID and no CACHE-CONTROL, LOCATION or SERVER; sending them on shutdown, on the interfaces being removed only, is `announce` and not done | UDA 2.0 clause 1.2.3 | `[part]` | `tests/test_advertise.py::test_byebye_message_has_no_cache_control_location_or_server`; `tests/test_advertise.py::test_every_alive_has_a_matching_byebye` | M2 |
| SSDP boot id, config id and `NEXTBOOTID.UPNP.ORG` handling: 31-bit BOOTID, CONFIGID 0 to 16777215, update message with a NEXTBOOTID above the BOOTID, and the state moves | UDA 2.0 clauses 1.2.2, 1.2.4 | `[ok]` | `tests/test_advertise.py::test_boot_and_config_ids`; `tests/test_advertise.py::test_update_message_carries_old_and_next_bootid`; `tests/test_advertise.py::test_config_refuses_what_the_clauses_forbid` | M2 |
| max-age re-advertisement and the random delay up to MX on search responses: `mx_delay` (0 to MX, an MX above 5 taken as 5) and `refresh_interval` (under half the max-age) are computed; the scheduler that applies them is `announce` and not done | UDA 2.0 clauses 1.2.2, 1.3.3 | `[part]` | `tests/test_advertise.py::test_mx_random_delay_is_bounded_by_mx_and_capped_at_five`; `tests/test_advertise.py::test_refresh_interval_is_under_half_the_max_age` | M2 |
| one LOCATION per interface for a multi-homed device | UDA 2.0 | `[ ]` | (to be written) | M2 |
| subscribe `CALLBACK` URL validation against SSRF: angle-bracketed `http://` URLs, IP literal host never a name, no credentials, no zone id, port 1 to 65535, local-network or same-host only, loopback on request, IPv4-mapped IPv6 judged by the mapped address, one bad URL fails the header, length never truncated; the specification names no such restriction, so this is design | UDA 2.0 clause 4.1.2 (design for the policy) | `[ok]` | `tests/test_events.py::test_hostile_callbacks_are_rejected_with_412`; `tests/test_events.py::test_callback_is_never_truncated_only_rejected`; `tests/test_events.py::test_same_host_policy_names_the_subscriber_only`; `tests/test_events.py::test_loopback_is_allowed_only_on_request` | M4 |
| subscription table with SID, timeout, per-subscription event key (0 first, then +1, wrapped from 4294967295 to 1), expiry sweep and 400, 412, 503 answers, and the NOTIFY message with SEQ; delivery with timeouts and backoff (`notify`) is not done | UDA 2.0 clauses 4.1.2 to 4.1.4, 4.3.2 | `[part]` | `tests/test_events.py::test_subscribe_assigns_sid_timeout_and_initial_event_key`; `tests/test_events.py::test_event_key_starts_at_zero_increments_and_wraps_to_one`; `tests/test_events.py::test_notify_message_layout_and_seq`; `tests/test_events.py::test_expired_subscriptions_are_swept_and_cannot_be_renewed` | M4 |
| SOAP `UPnPError` faults (`control.upnp_error_envelope`, `parse_upnp_error`, Table 3-3 codes, deprecated 403 and reserved 606 to 612 refused) and argument typing for the 26 dataType names (`scpd.coerce_argument`, errors 402 and 601); wiring the typing to a parsed SCPD needs `parse_scpd` | UDA 2.0 clauses 2.5, 3.2.5 | `[part]` | `tests/test_control_scpd.py::test_upnp_error_envelope_round_trips`; `tests/test_control_scpd.py::test_argument_typing_accepts_the_clause_2_5_forms`; `tests/test_control_scpd.py::test_argument_typing_refuses_with_the_table_3_3_code` | M3 |
| `example.basic-device`: an independent stdlib control point over loopback fetches the description, invokes an action and receives an event | UDA 2.0 | `[ ]` | (to be written) | M5 |
| UDA 2.0 section outline, `docs/uda-outline.md`: clause numbers and titles from the PDF's bookmarks (153 entries), the PDF's sha256, and a test that every clause the code cites exists; the per-row normative sentences are cited in docstrings and not copied | UDA 2.0 | `[part]` | `tests/test_docs.py::test_uda_outline_lists_every_cited_clause_with_its_title`; `tests/test_docs.py::test_uda_outline_records_the_pdf_it_was_read_from` | M1 |
| IPv6 SSDP scopes and messages (Annex A, read 2026-11-13 from the PDF, with Table A-1 through `pdftotext -table`, because `-layout` and `-raw` scramble it): `address_scope` and `ssdp_host_for` map a link-local address to `[FF02::C]:1900` and a ULA or GUA to `[FF05::C]:1900` and refuse temporary, 6to4, Teredo, ISATAP, loopback, multicast and IPv4-mapped addresses (A.2.3); a config whose host is an IPv6 group adds the OPT field with ns=01 and the NLS field (default the BOOTID, 1 to 64 characters) to alive, byebye, update and search-response messages (A.4.1 to A.4.6), and refuses a LOCATION that is an IPv4 literal or outside the group's scope (A.4.2); a multicast M-SEARCH to `[FF02::C]` or `[FF05::C]` is recognised and needs MX (A.4.5). Not done: the sockets, MLD joins, the hop limit of 10 for site scope, the 20 ms window across interfaces and one advertisement per address (all `announce`), and choosing among several addresses by RFC 6724 (A.2.3 items k and l) | UDA 2.0 Annex A.2.3, A.4, Table A-1 | `[part]` | `tests/test_advertise.py::test_ipv6_scope_selection`; `tests/test_advertise.py::test_ipv6_scope_selection_picks_the_group_and_refuses_the_rest`; `tests/test_advertise.py::test_ipv6_messages_carry_opt_and_nls`; `tests/test_advertise.py::test_ipv6_config_refuses_ipv4_and_out_of_scope_locations`; `tests/test_advertise.py::test_a_multicast_m_search_to_an_ipv6_group_needs_mx` | M2 |
| IPv6 eventing, Annex A.7: a CALLBACK of a SUBSCRIBE sent over IPv6 holds no IPv4 address and one sent over IPv4 holds no IPv6 address, and the delivery URL is the address the request came from for a link-local subscriber; `validate_callback` knows no address family of the request. The multicast event hosts `[FF02::130]:7900` and `[FF05::130]:7900` are accepted by `MulticastEvents` (row below) | UDA 2.0 Annex A.7 | `[ ]` | `tests/test_events.py::test_callback_family_follows_the_request` (to be written) | M4 |
| M-SEARCH with `TCPPORT.UPNP.ORG`: `tcp_search_reply` builds the one 200 OK that replies to all matching USNs, the USNs a comma-separated list, with no MX delay (clause 1.3.3); one message per distinct ST, because the clause does not say what ST a combined `ssdp:all` answer carries, so that grouping is this library's reading. Connecting to the control point's TCP port and writing the message is `announce` and not done | UDA 2.0 clauses 1.3.2, 1.3.3 | `[part]` | `tests/test_advertise.py::test_tcp_search_reply_is_one_message_listing_every_usn`; `tests/test_advertise.py::test_search_request_reads_the_control_point_headers` | M2 |
| `STATEVAR` and `ACCEPTED-STATEVAR` subscription handshake (clause 4.1.2): the table is given the service's evented variable names; a STATEVAR naming only those is recorded and `subscribe_response` writes the 200 OK with ACCEPTED-STATEVAR, `filter_properties` keeps an event to the listed variables; a STATEVAR naming an unimplemented variable, or any STATEVAR when the table does not know the service's variables, is not acknowledged and the subscription takes every evented variable; a renewal keeps the list. The initial event message, which carries "all evented variables or individual requested variables" (clause 4.3), is composed by the caller from `filter_properties` | UDA 2.0 clauses 4.1.2, 4.3 | `[ok]` | `tests/test_events.py::test_accepted_statevar_handshake`; `tests/test_events.py::test_a_statevar_naming_an_unimplemented_variable_is_not_acknowledged`; `tests/test_events.py::test_a_renewal_keeps_its_accepted_statevar_list`; `tests/test_events.py::test_subscribe_response_refuses_what_clause_4_1_2_does_not_allow` | M4 |
| NOTIFY with chunked transfer encoding (clause 4.3.2): `notify_message(..., chunk_size=)` writes TRANSFER-ENCODING chunked with no CONTENT-LENGTH and the body in chunks and a zero chunk, refused for HTTP/1.0; the clause's example writes the value in double quotes, which is not a valid HTTP transfer-coding, so it is written bare. Receiving a chunked NOTIFY is a control point's job and not done | UDA 2.0 clause 4.3.2 | `[ok]` | `tests/test_events.py::test_chunked_notify`; `tests/test_events.py::test_chunked_notify_is_refused_for_http_1_0_and_for_a_bad_size` | M4 |
| Multicast eventing messages (clauses 4.2, 4.3, 4.3.3, Annex A.7): `MulticastEvents` writes the NOTIFY with HOST (`239.255.255.246:7900` or `[FF0X::130]:7900`), USN, SVCID, NT, NTS, SEQ (0 first, wrapping to 1), LVL (Table 4-8 forms) and BOOTID.UPNP.ORG, never chunked, one UDP payload, with `messages` splitting a long variable list; retransmission re-sends the same bytes so the key is unchanged. The clause's example shows `NOTIFY * HTTP/1.0` while its field list says the request line "Shall be NOTIFY * HTTP/1.1"; the field list is followed. Not done: the UDP sending, the retransmission schedule (the working committees set it), the TTL of 2, and an event-level policy | UDA 2.0 clauses 4.2, 4.3, 4.3.3, Annex A.7 | `[part]` | `tests/test_events.py::test_multicast_event_message_layout`; `tests/test_events.py::test_multicast_event_key_wraps_from_the_maximum_to_one`; `tests/test_events.py::test_multicast_event_addresses_and_levels`; `tests/test_events.py::test_multicast_event_refuses_bad_fields`; `tests/test_events.py::test_a_multicast_event_is_one_udp_payload_and_may_be_split` | M4 |
| device protection headers: `SsdpConfig.securelocation` (an `https://` base URL) is written as SECURELOCATION.UPNP.ORG in alive, update and search-response messages (clauses 1.2.2, 1.2.4, 1.3.3), and `SearchRequest.cpfn` and `cpuuid` read CPFN.UPNP.ORG and CPUUID.UPNP.ORG from an M-SEARCH (a CPUUID that is not the clause 1.1.4 form is refused, a missing CPFN is not, though the clause says Required). The Device Protection service itself (its own document, TLS and the `<Name>`/`<Alias>` rule) is not read and not built; whether it is in scope is an owner decision | UDA 2.0 clauses 1.2.2, 1.3.2, 1.3.3 and the CPFN/CPUUID header clauses | `[part]` | `tests/test_advertise.py::test_securelocation_is_an_https_base_url_in_alive_update_and_search_response`; `tests/test_advertise.py::test_search_request_reads_the_control_point_headers` | - |
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
- Resolved 2026-11-13: the UDA 2.0 PDF does extract. `pdftotext -layout` gives 12,353 lines, and the primarysource `ecma` PDF reader (`primarysource/ecma/_pdf.py`, extractor `pdftotext`) cuts it into 153 sections whose ids are the clause numbers; they match the printed headings. The earlier note that no UDA section number could be verified is out of date; `docs/uda-outline.md` has the outline and the PDF's sha256. A table can scramble in `-layout` mode (Table 3-3, Table 4-4): read those with `pdftotext -raw`.
- UDA 2.0 cites obsolete or moved references: RFC 2616 (DATE format, request-target) is obsoleted by RFC 7230 to 7235 and so by RFC 9110 and RFC 9112; RFC 2141 (hyphens for periods in vendor domain names) is obsoleted by RFC 8141; RFC 4340 (DCCP) is cited only for the dynamic port range 49152 to 65535, which RFC 6335 now defines; RFC 3986 is current. The Date header written by `search_response` is the RFC 1123 form, which RFC 9110 keeps as IMF-fixdate.
- The PDF's footer reads 2015 Open Connectivity Foundation while the title page gives the revision date April 17, 2020; the document's own SERVER and USER-AGENT examples say UPnP/2.0.
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
