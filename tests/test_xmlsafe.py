"""xmlsafe.parse refuses what a stranger on the LAN can send. Vectors are written here."""

from __future__ import annotations

import socket
import time
import xml.etree.ElementTree as ET

import pytest

from devicespy import xmlsafe
from devicespy.xmlsafe import (
    XmlForbidden,
    XmlMalformed,
    XmlRefused,
    XmlTooDeep,
    XmlTooLarge,
    localname,
    parse,
)

BIG = 1_000_000


def test_plain_document_parses_and_returns_root():
    root = parse(b'<?xml version="1.0"?><a x="1">hi<b>t</b>tail<c/></a>', BIG)
    assert root.tag == "a"
    assert root.get("x") == "1"
    assert root.text == "hi"
    assert [c.tag for c in root] == ["b", "c"]
    assert root[0].text == "t"
    assert root[0].tail == "tail"


def test_utf8_declaration_and_bom_are_accepted():
    root = parse(b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><a>\xc3\xa9</a>', BIG)
    assert root.text == "é"


def test_refuses_doctype():
    with pytest.raises(XmlForbidden):
        parse(b"<!DOCTYPE x><x/>", BIG)


def test_refuses_internal_entity_declaration():
    laughs = (
        b'<?xml version="1.0"?><!DOCTYPE lolz ['
        b'<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
        b'<!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">'
        b"]><lolz>&lol4;</lolz>"
    )
    start = time.perf_counter()
    with pytest.raises(XmlForbidden):
        parse(laughs, BIG)
    assert time.perf_counter() - start < 1.0


def test_refuses_external_entity_reference(monkeypatch, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    opened = []
    real_connect = socket.socket.connect

    def spy_connect(self, address):
        opened.append(address)
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", spy_connect)
    for target in (secret.as_uri(), "http://127.0.0.1:9/x"):
        doc = f'<!DOCTYPE x [<!ENTITY e SYSTEM "{target}">]><x>&e;</x>'.encode()
        with pytest.raises(XmlForbidden):
            parse(doc, BIG)
    assert opened == []


def test_refuses_parameter_entity():
    doc = b'<!DOCTYPE x [<!ENTITY % p SYSTEM "http://127.0.0.1:9/p.dtd"> %p;]><x/>'
    with pytest.raises(XmlForbidden):
        parse(doc, BIG)


def test_undeclared_entity_reference_is_refused():
    with pytest.raises(XmlMalformed):
        parse(b"<x>&nope;</x>", BIG)


def test_predefined_entities_still_work():
    assert parse(b"<x>&lt;&amp;&gt;</x>", BIG).text == "<&>"


def test_refuses_processing_instruction():
    with pytest.raises(XmlForbidden):
        parse(b'<?xml-stylesheet href="x"?><x/>', BIG)
    with pytest.raises(XmlForbidden):
        parse(b"<x><?php evil ?></x>", BIG)


def test_processing_instruction_can_be_ignored_when_asked():
    root = parse(b"<x><?pi data?>t</x>", BIG, ignore_processing_instructions=True)
    assert root.text == "t"


def test_depth_limit():
    ok = b"<a>" * 32 + b"</a>" * 32
    parse(ok, BIG)
    with pytest.raises(XmlTooDeep):
        parse(b"<a>" * 33 + b"</a>" * 33, BIG)
    parse(b"<a>" * 33 + b"</a>" * 33, BIG, max_depth=33)


def test_element_limit():
    doc = b"<r>" + b"<e/>" * 10 + b"</r>"
    parse(doc, BIG, max_elements=11)
    with pytest.raises(XmlTooLarge):
        parse(doc, BIG, max_elements=10)


def test_size_limit_is_checked_before_parse(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("parser was reached")

    monkeypatch.setattr(xmlsafe.expat, "ParserCreate", explode)
    with pytest.raises(XmlTooLarge):
        parse(b"<a/>", 3)


def test_size_limit_is_inclusive():
    assert parse(b"<a/>", 4).tag == "a"


def test_huge_attribute_refused():
    doc = b'<a x="' + b"A" * 9000 + b'"/>'
    with pytest.raises(XmlTooLarge):
        parse(doc, BIG)
    assert parse(doc, BIG, max_attribute_length=9000).get("x") == "A" * 9000


def test_attribute_count_refused():
    attrs = b" ".join(b'a%d="1"' % i for i in range(65))
    with pytest.raises(XmlTooLarge):
        parse(b"<e " + attrs + b"/>", BIG)


def test_namespace_split_for_default_and_prefixed_names():
    doc = (
        b'<r xmlns="urn:schemas-upnp-org:device-1-0" xmlns:p="urn:other" p:attr="v">'
        b"<p:x/><y xmlns=''/></r>"
    )
    root = parse(doc, BIG)
    assert localname(root.tag) == ("urn:schemas-upnp-org:device-1-0", "r")
    assert localname(root[0].tag) == ("urn:other", "x")
    assert localname(root[1].tag) == ("", "y")
    assert localname("{urn:other}attr") == ("urn:other", "attr")
    assert root.get("{urn:other}attr") == "v"


def test_prefix_is_irrelevant():
    a = parse(b'<s:r xmlns:s="urn:n"><s:c/></s:r>', BIG)
    b = parse(b'<q:r xmlns:q="urn:n"><q:c/></q:r>', BIG)
    assert ET.tostring(a, encoding="unicode").count("urn:n") == 1
    assert (a.tag, a[0].tag) == (b.tag, b[0].tag) == ("{urn:n}r", "{urn:n}c")


@pytest.mark.parametrize("doc", [b"<a><b>", b"<a></b>", b"<a", b"plain text", b"<a/><b/>"])
def test_truncated_and_malformed_input_refused(doc):
    with pytest.raises(XmlMalformed):
        parse(doc, BIG)


def test_non_utf8_input_refused():
    with pytest.raises(XmlRefused):
        parse(b"<a>\xff\xfe</a>", BIG)
    with pytest.raises(XmlRefused):
        parse("<a>x</a>".encode("utf-16"), BIG)


def test_empty_input_refused():
    with pytest.raises(XmlMalformed):
        parse(b"", BIG)
    with pytest.raises(XmlMalformed):
        parse(b"   \n", BIG)


def test_encoding_other_than_utf8_is_refused():
    doc = '<?xml version="1.0" encoding="ISO-8859-1"?><a>\xe9</a>'.encode("latin-1")
    with pytest.raises(XmlForbidden):
        parse(doc, BIG)


def test_every_refusal_is_a_value_error_with_a_reason():
    with pytest.raises(ValueError, match="empty") as info:
        parse(b"", BIG)
    assert isinstance(info.value, XmlRefused)
    assert info.value.reason == "empty document"


def test_str_input_is_a_type_error():
    with pytest.raises(TypeError):
        parse("<a/>", BIG)
