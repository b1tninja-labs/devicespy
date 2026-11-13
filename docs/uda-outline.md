# UPnP Device Architecture 2.0: section outline

Read on 2026-11-13 from the Open Connectivity Foundation's PDF (document revision date 2020-04-17,
sha256 9aa6eb29dfcdbe8991a667f8c9a3f47d532438082354b79f5c744b4b7618f202), using the PDF's own bookmark
outline through the primarysource `ecma` reader (`pdftotext` as the extractor, 197 pages).
The section numbers below are the ones the PDF's bookmarks carry; they were cross-checked against the
printed headings for every clause this repository cites. Only numbers and titles are recorded here: the
specification's text is not vendored.

Clauses cited by code or tests so far: 1.1.4, 1.2.2, 1.2.3, 1.2.4, 1.3.2, 1.3.3, 2.5 (dataType list),
3.2.5 (Table 3-3), 4.1.2, 4.1.3, 4.1.4 (Tables 4-4 to 4-6), 4.3.2.

| Clause | Title |
|---|---|
| 1 | Discovery |
| 1.1 | SSDP message format |
| 1.1.1 | SSDP Start-line |
| 1.1.2 | SSDP message header fields |
| 1.1.3 | SSDP header field extensions |
| 1.1.4 | UUID format and recommended generation algorithms |
| 1.1.5 | SSDP processing rules |
| 1.2 | Advertisement |
| 1.2.1 | Advertisement protocols and standards |
| 1.2.2 | Device available - NOTIFY with ssdp:alive |
| 1.2.3 | Device unavailable -- NOTIFY with ssdp:byebye |
| 1.2.4 | Device Update – NOTIFY with ssdp:update |
| 1.3 | Search |
| 1.3.1 | Search protocols and standards |
| 1.3.2 | Search request with M-SEARCH |
| 1.3.3 | Search response |
| 1.4 | References |
| 2 | Description |
| 2.1 | Generic requirements on HTTP usage |
| 2.2 | Generic requirements on XML usage |
| 2.3 | Device description |
| 2.4 | UPnP Device Template |
| 2.5 | Service description |
| 2.5.1 | Defining and processing extended data types |
| 2.5.2 | String equivalents of extended data types |
| 2.5.3 | Generic requirements |
| 2.5.4 | Ordering of Elements |
| 2.5.5 | Versioning |
| 2.6 | UPnP Service Template |
| 2.7 | Non-standard vendor extensions and limitations |
| 2.7.1 | Placement of Additional Elements and Attributes |
| 2.8 | UPnP Device Schema |
| 2.9 | UPnP Service Schema |
| 2.10 | UPnP Datatype Schema |
| 2.11 | Retrieving a description using HTTP |
| 2.12 | References |
| 3 | Control |
| 3.1 | Control protocols |
| 3.1.1 | SOAP Profile |
| 3.2 | Actions |
| 3.2.1 | Action invocation |
| 3.2.2 | Action Response |
| 3.2.3 | UPnP Action Schema |
| 3.2.4 | Recommendations and additional requirements |
| 3.2.5 | Action error response |
| 3.2.6 | UPnP Error Schema |
| 3.3 | Query for variable |
| 3.4 | References |
| 4 | Eventing |
| 4.1 | Unicast eventing |
| 4.1.1 | Subscription |
| 4.1.2 | SUBSCRIBE with NT and CALLBACK |
| 4.1.3 | Renewing a subscription with SUBSCRIBE with SID |
| 4.1.4 | Canceling a subscription with UNSUBSCRIBE |
| 4.2 | Multicast Eventing |
| 4.3 | Event messages |
| 4.3.1 | Error Cases |
| 4.3.2 | Unicast eventing: Event messages: NOTIFY |
| 4.3.3 | Multicast Eventing: Event messages: NOTIFY |
| 4.4 | UPnP Event Schema |
| 4.5 | Augmenting the UPnP Device and Service Schemas |
| 4.6 | References |
| 5 | Presentation |
| 5.1 | References |
| A | (normative) IP Version 6 Support |
| A.0 | Note (informative) |
| A.1 | Introduction |
| A.2 | General Principles |
| A.2.1 | UPnP Device Architecture V1.0 |
| A.2.2 | UPnP Device Architecture V2.0 |
| A.2.3 | IPv6 and Dual Stack |
| A.2.4 | Device operation |
| A.2.5 | Control point operation |
| A.3 | Addressing |
| A.3.1 | UPnP Messaging on IPv6 Interfaces |
| A.3.2 | Summary of boot/startup process |
| A.3.3 | Address Selection and RFC 6724 |
| A.4 | Discovery |
| A.4.1 | OPT and NLS |
| A.4.2 | Advertisement |
| A.4.3 | Advertisement: Device unavailable |
| A.4.4 | Advertisement: Device update |
| A.4.5 | Search |
| A.4.6 | Search response |
| A.5 | Description |
| A.6 | Control |
| A.7 | Eventing |
| A.8 | Presentation |
| A.9 | References |
| A.9.1 | Normative |
| A.9.2 | Informative |
| B | Schemas |
| B.1 | UPnP Device Schema |
| B.2 | UPnP Service Schema |
| B.3 | UPnP Control Schema |
| B.4 | UPnP Error Schema |
| B.5 | UPnP Event Schema |
| B.6 | UPnP Cloud Schema |
| B.7 | Schema references |
| C | Cloud |
| C.1 | Introduction |
| C.1.1 | What is UPnP™ Cloud Technology (UCA)? |
| C.1.2 | Audience |
| C.1.3 | In this Annex |
| C.1.4 | UDA compared to UCA |
| C.1.5 | UCA General Communications Paths |
| C.1.6 | UCA Specific Communication Paths |
| C.1.7 | UCA Steps as Analogies to UDA |
| C.2 | Terms and Definitions |
| C.2.1 | Acronyms |
| C.2.2 | General Cloud Terms and Definitions |
| C.2.3 | Device and Control Point Terms and Definitions |
| C.2.4 | Service Terms and Definitions |
| C.2.5 | Groups |
| C.3 | References |
| C.4 | General XMPP Features |
| C.4.1 | XMPP Jabber IDs or JIDs |
| C.4.1.1 | XMPP stanzas |
| C.4.1.2 | <iq> stanzas |
| C.4.1.3 | <presence> stanzas |
| C.4.1.4 | <message> stanzas |
| C.5 | Creating a Device or Control Point Resource |
| C.5.1 | Finding a UCS |
| C.5.2 | Account Creation |
| C.5.3 | Authentication |
| C.5.4 | Binding Devices and Control Points as a Resource |
| C.5.4.1 | Limitations on stanza redirection. |
| C.5.4.2 | Handling resource priority |
| C.5.5 | Embedded Devices |
| C.6 | Presence and Discovery |
| C.6.1 | Presence (Analog to NOTIFY with ssdp:alive) |
| C.6.2 | XMPP disco#items (analog to M-SEARCH for users UCCDs and UCC-CPs) |
| C.6.3 | Presence update (analog to NOTIFY with ssdp:update) |
| C.6.4 | Presence "unavailable" (Analog to NOTIFY with ssdp:byebye) |
| C.6.5 | Service Level Discovery |
| C.6.6 | IQ:Query for DDD and SCPD Exchange (analog of HTTP GET for DDD and SCPD) |
| C.6.6.1 | DDD and SCPD "get" |
| C.6.6.2 | DDD and SCPD "result" or "error" |
| C.6.6.3 | Exchange of Device Icons |
| C.7 | PubSub (Analog of Eventing) |
| C.7.1 | Creating the UCCD PubSub structure |
| C.7.1.1 | Verifying an existing UCCD PubSub Hierarchy |
| C.7.2 | Creating a UCCD PubSub collection |
| C.7.3 | Publishing a UCCD PubSub event |
| C.7.4 | Subscribing to a UCCD PubSub collection |
| C.7.5 | Unsubscribing to a UCCD PubSub collection |
| C.7.6 | Permissions model |
| C.8 | SOAP over XMPP (Analog of Control) |
| C.9 | Support for Binary (Media) Transport |
| C.10 | UCA errorCodes |
| C.11 | UCA Schemas |
| C.12 | Closing a UCA Session |
| C.13 | UCA over BOSH and WebSocket |
