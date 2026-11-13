"""The hardened XML reader every other module must use, by design.

UPnP and CWMP peers are strangers on a network, so the document is hostile until parsed. This
reader is built straight on ``xml.parsers.expat`` and refuses, rather than defends against:

- any document type declaration (so no internal or external entity can be declared, and
  billion-laughs style expansion is impossible), plus any entity or parameter-entity
  declaration or external reference should one reach a handler anyway;
- any processing instruction other than the XML declaration;
- any declared encoding other than UTF-8;
- input larger than ``limit`` bytes, deeper than ``max_depth``, with more than
  ``max_elements`` elements, more than ``max_attributes`` attributes on one element, or an
  attribute value longer than ``max_attribute_length`` characters.

Every refusal is an :class:`XmlRefused` carrying a short ``reason``. The result is an
``xml.etree.ElementTree.Element`` whose names are in ElementTree's ``{namespace}local`` form;
namespace prefixes are not preserved, so callers match on the namespace URI.

The rules are a design decision of this project and not a requirement of the UPnP Device
Architecture 2.0 (2020-04-17) or of TR-069; XML 1.0 itself is a W3C Recommendation, see
``docs/rfc-map.md``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING
from xml.parsers import expat

if TYPE_CHECKING:
    from typing import NoReturn

__all__ = [
    "XmlForbidden",
    "XmlMalformed",
    "XmlRefused",
    "XmlTooDeep",
    "XmlTooLarge",
    "localname",
    "parse",
]

_SEP = "}"


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
    ) -> None:
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
        element = ET.Element(_qname(name), {_qname(k): v for k, v in attrs.items()})
        if self.stack:
            self.stack[-1].append(element)
        else:
            self.root = element
        self.stack.append(element)
        self.tail_of = None

    def end(self, _name: str) -> None:
        self.tail_of = self.stack.pop()

    def data(self, text: str) -> None:
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
    builder = _Builder(max_depth, max_elements, max_attributes, max_attribute_length)
    parser = expat.ParserCreate(None, _SEP)
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartDoctypeDeclHandler = builder.refuse
    parser.EntityDeclHandler = builder.refuse
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
