"""The hardened XML reader every other module must use, by design.

UPnP and CWMP peers are strangers on a network, so the document is hostile until parsed. This
reader is built straight on ``xml.parsers.expat`` and refuses, rather than defends against:

- any document type declaration (so no internal or external entity can be declared, and
  billion-laughs style expansion is impossible), plus any entity or parameter-entity
  declaration or external reference should one reach a handler anyway. The one exception is a
  document whose sha256 is on the pin list (:data:`PINNED_DTD_FILES`, see below);
- any processing instruction other than the XML declaration;
- any declared encoding other than UTF-8;
- input larger than ``limit`` bytes, deeper than ``max_depth``, with more than
  ``max_elements`` elements, more than ``max_attributes`` attributes on one element, or an
  attribute value longer than ``max_attribute_length`` characters.

**The pin list.** Broadband Forum's ``tr-106-types.xml`` declares a handful of general entities
(``&octet;`` and friends) in an internal DTD subset, so refusing every DTD would refuse the file TR-181 data
models import. A document is accepted with a DTD only when the sha256 of its exact bytes is a key of the pin
list; a file one byte different is unpinned and is refused exactly as before. For a pinned file the DTD is
still tightly bounded: no external identifier on the document type, no parameter entity, no external or
unparsed entity, no notation, no element or attribute-list declaration, at most ``max_entities`` entities, each
value at most ``max_entity_length`` characters and containing no reference to another entity (so an entity
cannot grow by nesting), and the text of the document, after expansion, is held to ``max_text``.

Every refusal is an :class:`XmlRefused` carrying a short ``reason``. The result is an
``xml.etree.ElementTree.Element`` whose names are in ElementTree's ``{namespace}local`` form;
namespace prefixes are not preserved, so callers match on the namespace URI.

The rules are a design decision of this project and not a requirement of the UPnP Device
Architecture 2.0 (2020-04-17) or of TR-069; XML 1.0 itself is a W3C Recommendation, see
``docs/rfc-map.md``.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.parsers import expat

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import NoReturn

__all__ = [
    "PINNED_DTD_FILES",
    "PinnedDtd",
    "XmlForbidden",
    "XmlMalformed",
    "XmlRefused",
    "XmlTooDeep",
    "XmlTooLarge",
    "localname",
    "parse",
]

_SEP = "}"


@dataclass(frozen=True, slots=True)
class PinnedDtd:
    """A file that may carry an internal DTD subset of general entities, identified by its bytes."""

    name: str
    sha256: str
    size: int
    read: str


#: sha256 of the exact bytes -> the pinned file. Only the entries here lift the DTD refusal.
PINNED_DTD_FILES: Mapping[str, PinnedDtd] = {
    "68237466c70b9f48ea647878af65d54c16a42e45d2ef2ba5f6e4a1042e0484a1": PinnedDtd(
        name="tr-106-types.xml",
        sha256="68237466c70b9f48ea647878af65d54c16a42e45d2ef2ba5f6e4a1042e0484a1",
        size=21157,
        read="https://cwmp-data-models.broadband-forum.org/tr-106-types.xml, fetched 2026-11-13; "
        "its header grants BSD-3-Clause-style redistribution with the notice retained",
    ),
}

_ENTITY_REF = re.compile(r"&")


class XmlRefused(ValueError):  # noqa: N818 - the name is the contract
    """The document was refused; ``reason`` says why in one short phrase."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class XmlTooLarge(XmlRefused):
    """A size limit was exceeded: bytes, element count, attribute count or attribute length."""


class XmlTooDeep(XmlRefused):
    """Element nesting went past ``max_depth``."""


class XmlForbidden(XmlRefused):
    """A construct this reader never accepts: DTD, entity, processing instruction, encoding."""


class XmlMalformed(XmlRefused):
    """Not well-formed XML, including empty and truncated input."""


def _qname(name: str) -> str:
    # expat with a namespace separator yields "uri}local" (the local part cannot contain it).
    if _SEP in name:
        uri, local = name.rsplit(_SEP, 1)
        return "{" + uri + "}" + local
    return name


def localname(tag: str) -> tuple[str, str]:
    """Split an ElementTree name ``{namespace}local`` into ``(namespace, local)``.

    A name with no namespace gives ``("", name)``. UPnP Device Architecture 2.0 (2020-04-17)
    matches on namespace URI, never on prefix, so callers compare both parts.
    """
    if tag.startswith("{"):
        uri, sep, local = tag[1:].partition("}")
        if sep:
            return uri, local
    return "", tag


class _Builder:
    def __init__(
        self,
        max_depth: int,
        max_elements: int,
        max_attributes: int,
        max_attribute_length: int,
        raw: bytes = b"",
        pins: Mapping[str, PinnedDtd] | None = None,
        max_entities: int = 0,
        max_entity_length: int = 0,
        max_text: int = 0,
    ) -> None:
        self.raw = raw
        self.pins = pins
        self.pinned: PinnedDtd | None = None
        self.max_entities = max_entities
        self.max_entity_length = max_entity_length
        self.max_text = max_text
        self.entities = 0
        self.text = 0
        self.max_depth = max_depth
        self.max_elements = max_elements
        self.max_attributes = max_attributes
        self.max_attribute_length = max_attribute_length
        self.stack: list[ET.Element] = []
        self.root: ET.Element | None = None
        self.count = 0
        self.tail_of: ET.Element | None = None

    def refuse(self, *_args: object) -> NoReturn:
        raise XmlForbidden("document type declarations and entities are not accepted")

    def doctype(
        self, _name: str, system_id: str | None, public_id: str | None, _has_internal: bool
    ) -> None:
        pin = (self.pins or {}).get(hashlib.sha256(self.raw).hexdigest())
        if pin is None or pin.size != len(self.raw):
            self.refuse()
        if system_id is not None or public_id is not None:
            raise XmlForbidden("a pinned document may not name an external DTD")
        self.pinned = pin

    def entity(
        self,
        name: str,
        is_parameter: int,
        value: str | None,
        _base: str | None,
        system_id: str | None,
        _public_id: str | None,
        notation: str | None,
    ) -> None:
        if self.pinned is None:
            self.refuse()
        if is_parameter:
            raise XmlForbidden("parameter entities are not accepted")
        if value is None or system_id is not None or notation is not None:
            raise XmlForbidden("external and unparsed entities are not accepted")
        self.entities += 1
        if self.entities > self.max_entities:
            raise XmlTooLarge(f"more than {self.max_entities} entities")
        if len(value) > self.max_entity_length:
            raise XmlTooLarge(f"entity {name} longer than {self.max_entity_length}")
        if _ENTITY_REF.search(value):
            raise XmlForbidden(f"entity {name} refers to another entity")

    def refuse_markup_decl(self, *_args: object) -> NoReturn:
        raise XmlForbidden("element and attribute-list declarations are not accepted")

    def refuse_pi(self, *_args: object) -> NoReturn:
        raise XmlForbidden("processing instructions are not accepted")

    def xml_decl(self, _version: str, encoding: str | None, _standalone: int) -> None:
        if encoding is not None and encoding.lower() not in ("utf-8", "utf8"):
            raise XmlForbidden("only UTF-8 is accepted, document declares " + encoding)

    def start(self, name: str, attrs: dict[str, str]) -> None:
        if len(self.stack) >= self.max_depth:
            raise XmlTooDeep(f"nesting deeper than {self.max_depth}")
        self.count += 1
        if self.count > self.max_elements:
            raise XmlTooLarge(f"more than {self.max_elements} elements")
        if len(attrs) > self.max_attributes:
            raise XmlTooLarge(f"more than {self.max_attributes} attributes on one element")
        for value in attrs.values():
            if len(value) > self.max_attribute_length:
                raise XmlTooLarge(f"attribute value longer than {self.max_attribute_length}")
            self.count_text(len(value))
        element = ET.Element(_qname(name), {_qname(k): v for k, v in attrs.items()})
        if self.stack:
            self.stack[-1].append(element)
        else:
            self.root = element
        self.stack.append(element)
        self.tail_of = None

    def end(self, _name: str) -> None:
        self.tail_of = self.stack.pop()

    def count_text(self, size: int) -> None:
        self.text += size
        if self.text > self.max_text:
            raise XmlTooLarge(f"more than {self.max_text} characters of text after expansion")

    def data(self, text: str) -> None:
        self.count_text(len(text))
        if self.tail_of is not None:
            self.tail_of.tail = (self.tail_of.tail or "") + text
        elif self.stack:
            top = self.stack[-1]
            top.text = (top.text or "") + text


def parse(
    raw: bytes,
    limit: int,
    *,
    max_depth: int = 32,
    max_elements: int = 50_000,
    max_attributes: int = 64,
    max_attribute_length: int = 8192,
    ignore_processing_instructions: bool = False,
    pins: Mapping[str, PinnedDtd] | None = PINNED_DTD_FILES,
    max_entities: int = 64,
    max_entity_length: int = 1024,
    max_text: int | None = None,
) -> ET.Element:
    """Parse ``raw`` into an Element, or raise :class:`XmlRefused`; refusal is by design.

    ``limit`` is the largest acceptable ``len(raw)`` and is checked before any parsing.
    The whole document must be passed at once. The returned root is never a placeholder:
    empty, truncated, non-UTF-8 and over-limit input all raise. The rules are listed in the
    module docstring and are this project's design, not a UPnP Device Architecture 2.0
    (2020-04-17) requirement.

    Processing instructions are refused unless ``ignore_processing_instructions`` is true, in
    which case they are dropped; TR-069 Amendment 6 Corrigendum 1 section 3.5 lets a CWMP
    receiver ignore them, so cwmp passes true.

    A DTD is refused unless the sha256 of ``raw`` is a key of ``pins`` (default
    :data:`PINNED_DTD_FILES`); pass ``pins={}`` to refuse every DTD whatever the module list says.
    ``max_text`` bounds the characters of text and attribute values after expansion and defaults to
    four times ``limit``.
    """
    if not isinstance(raw, bytes | bytearray | memoryview):
        raise TypeError("raw must be bytes")
    if limit < 0:
        raise ValueError("limit must not be negative")
    if len(raw) > limit:
        raise XmlTooLarge(f"{len(raw)} bytes exceeds the limit of {limit}")
    if not len(raw):
        raise XmlMalformed("empty document")
    head = bytes(raw[:4])
    if head[:2] in (b"\xfe\xff", b"\xff\xfe") or b"\x00" in head:
        raise XmlForbidden("only UTF-8 is accepted, input looks like UTF-16 or UTF-32")
    builder = _Builder(
        max_depth,
        max_elements,
        max_attributes,
        max_attribute_length,
        raw=bytes(raw),
        pins=pins,
        max_entities=max_entities,
        max_entity_length=max_entity_length,
        max_text=4 * limit if max_text is None else max_text,
    )
    parser = expat.ParserCreate(None, _SEP)
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartDoctypeDeclHandler = builder.doctype
    parser.EntityDeclHandler = builder.entity
    parser.ElementDeclHandler = builder.refuse_markup_decl
    parser.AttlistDeclHandler = builder.refuse_markup_decl
    parser.ExternalEntityRefHandler = builder.refuse
    parser.NotationDeclHandler = builder.refuse
    if not ignore_processing_instructions:
        parser.ProcessingInstructionHandler = builder.refuse_pi
    parser.XmlDeclHandler = builder.xml_decl
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data
    try:
        parser.Parse(bytes(raw), True)
    except XmlRefused:
        raise
    except expat.ExpatError as error:
        raise XmlMalformed(expat.ErrorString(error.code)) from None
    if builder.root is None:
        raise XmlMalformed("no root element")
    return builder.root
