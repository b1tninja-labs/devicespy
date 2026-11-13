"""xmlsafe.parse refuses what a stranger on the LAN can send. Vectors are written here."""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

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


# --- the sha256 pin list -----------------------------------------------------------------


def _pins_for(doc: bytes) -> dict[str, xmlsafe.PinnedDtd]:
    digest = hashlib.sha256(doc).hexdigest()
    return {digest: xmlsafe.PinnedDtd("test.xml", digest, len(doc), "written in this test")}


_TYPES_LIKE = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<!DOCTYPE t [\n<!ENTITY octet "(25[0-5]|2[0-4][0-9])">\n<!ENTITY dot "\\.">\n]>\n'
    b'<t><p value="(&octet;&dot;){3}&octet;"/></t>'
)


def test_pinned_file_may_declare_internal_general_entities():
    root = parse(_TYPES_LIKE, BIG, pins=_pins_for(_TYPES_LIKE))
    assert root[0].get("value") == r"((25[0-5]|2[0-4][0-9])\.){3}(25[0-5]|2[0-4][0-9])"


def test_the_same_file_is_refused_when_it_is_not_pinned():
    with pytest.raises(XmlForbidden):
        parse(_TYPES_LIKE, BIG)
    with pytest.raises(XmlForbidden):
        parse(_TYPES_LIKE, BIG, pins={})


def test_one_changed_byte_unpins_a_file():
    pins = _pins_for(_TYPES_LIKE)
    with pytest.raises(XmlForbidden):
        parse(_TYPES_LIKE + b" ", BIG, pins=pins)


def test_a_pin_with_the_wrong_size_does_not_match():
    digest = hashlib.sha256(_TYPES_LIKE).hexdigest()
    pins = {digest: xmlsafe.PinnedDtd("x", digest, len(_TYPES_LIKE) + 1, "wrong size")}
    with pytest.raises(XmlForbidden):
        parse(_TYPES_LIKE, BIG, pins=pins)


_HOSTILE = {
    "billion laughs": (
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
        b'<!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">]>'
        b"<lolz>&lol4;</lolz>"
    ),
    "char-reference nesting": (
        b'<!DOCTYPE x [<!ENTITY a "lol"><!ENTITY b "&#38;a;&#38;a;">]><x>&b;</x>'
    ),
    "external entity": b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>',
    "external public entity": (
        b'<!DOCTYPE x [<!ENTITY e PUBLIC "-//X//Y" "http://127.0.0.1:9/e">]><x>&e;</x>'
    ),
    "unparsed entity": b'<!DOCTYPE x [<!NOTATION n SYSTEM "n"><!ENTITY e SYSTEM "e" NDATA n>]><x/>',
    "parameter entity": b"<!DOCTYPE x [<!ENTITY % p \"<!ENTITY e 'v'>\"> %p;]><x>&e;</x>",
    "external parameter entity": (
        b'<!DOCTYPE x [<!ENTITY % p SYSTEM "http://127.0.0.1:9/p.dtd"> %p;]><x/>'
    ),
    "external DTD": b'<!DOCTYPE x SYSTEM "http://127.0.0.1:9/x.dtd"><x/>',
    "element declaration": b"<!DOCTYPE x [<!ELEMENT x ANY>]><x/>",
    "attribute-list default": b'<!DOCTYPE x [<!ATTLIST x a CDATA "d">]><x/>',
    "long entity": b'<!DOCTYPE x [<!ENTITY e "' + b"a" * 2000 + b'">]><x>&e;</x>',
    "many entities": (
        b"<!DOCTYPE x [" + b"".join(b'<!ENTITY e%d "v">' % i for i in range(100)) + b"]><x/>"
    ),
}


@pytest.mark.parametrize("name", sorted(_HOSTILE))
def test_hostile_dtds_are_refused_unpinned(name):
    start = time.perf_counter()
    with pytest.raises(XmlRefused):
        parse(_HOSTILE[name], BIG)
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("name", sorted(_HOSTILE))
def test_hostile_dtds_are_refused_even_when_pinned(name, monkeypatch):
    doc = _HOSTILE[name]
    opened = []
    real_connect = socket.socket.connect

    def spy_connect(self, address):
        opened.append(address)
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", spy_connect)
    start = time.perf_counter()
    with pytest.raises(XmlRefused):
        parse(doc, BIG, pins=_pins_for(doc))
    assert time.perf_counter() - start < 1.0
    assert opened == []


def test_expanded_text_is_bounded_for_a_pinned_file():
    doc = b'<!DOCTYPE x [<!ENTITY e "' + b"a" * 1000 + b'">]><x>' + b"&e;" * 200 + b"</x>"
    with pytest.raises(XmlTooLarge):
        parse(doc, BIG, pins=_pins_for(doc), max_text=50_000)
    assert len(parse(doc, BIG, pins=_pins_for(doc)).text or "") == 200_000


def test_the_pin_list_names_tr_106_types():
    assert [p.name for p in xmlsafe.PINNED_DTD_FILES.values()] == ["tr-106-types.xml"]
    for digest, pin in xmlsafe.PINNED_DTD_FILES.items():
        assert digest == pin.sha256
        assert len(digest) == 64
        assert pin.size > 0
        assert pin.read


def _cached_types() -> Path | None:
    base = os.environ.get("CWMP_DATA_CACHE")
    if base:
        root = Path(base)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "cwmp-data"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "cwmp-data"
    path = root / "tr-106-types.xml"
    return path if path.is_file() else None


def test_the_real_tr_106_types_parses_when_the_cache_has_it():
    path = _cached_types()
    if path is None:
        pytest.skip(
            "SKIPPED LOUDLY: tr-106-types.xml is not in the cache; run ../cwmp/tools/fetch_bbf.py"
        )
    raw = path.read_bytes()
    pin = next(iter(xmlsafe.PINNED_DTD_FILES.values()))
    assert hashlib.sha256(raw).hexdigest() == pin.sha256
    assert len(raw) == pin.size
    root = parse(raw, 1_000_000)
    assert xmlsafe.localname(root.tag) == (
        "urn:broadband-forum-org:cwmp:datamodel-1-14",
        "document",
    )
    values = [e.get("value") or "" for e in root.iter("pattern")]
    assert not any("&" in v for v in values)
    assert any("25[0-5]" in v for v in values)
    with pytest.raises(XmlForbidden):
        parse(raw, 1_000_000, pins={})


# -- allow_external_id: a bare DOCTYPE naming an external identifier, never fetched ------------------

_SYS = b'<!DOCTYPE glsa SYSTEM "http://www.gentoo.org/dtd/glsa.dtd">'
_PUB = b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0//EN" "http://example.invalid/x.dtd">'


def _ext(raw: bytes) -> ET.Element:
    return parse(raw, BIG, allow_external_id=True)


def test_external_id_option_is_off_by_default():
    with pytest.raises(XmlForbidden):
        parse(_SYS + b"<glsa/>", BIG)


def test_external_id_system_and_public_are_accepted_with_the_option():
    assert (
        _ext(b'<?xml version="1.0"?>\n' + _SYS + b"\n<glsa id='1'><t>x</t></glsa>").get("id") == "1"
    )
    assert _ext(_PUB + b"<html/>").tag == "html"


def test_external_id_is_never_fetched(monkeypatch):
    opened = []

    def spy(self, address):
        opened.append(address)
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", spy)
    monkeypatch.setattr(socket.socket, "connect_ex", spy)
    _ext(_SYS + b"<glsa/>")
    assert opened == []


@pytest.mark.parametrize(
    "doc",
    [
        b'<!DOCTYPE a SYSTEM "x.dtd" [<!ENTITY e "v">]><a>&e;</a>',
        b'<!DOCTYPE a SYSTEM "x.dtd" []><a/>',
        b'<!DOCTYPE a [<!ENTITY e "v">]><a>&e;</a>',
        b"<!DOCTYPE a><a/>",
        b'<!DOCTYPE a SYSTEM "x.dtd" [<!ELEMENT a ANY>]><a/>',
        b'<!DOCTYPE a SYSTEM "x.dtd" [<!ENTITY % p "x">]><a/>',
        b'<!DOCTYPE a SYSTEM "x.dtd" [<!ENTITY x SYSTEM "file:///etc/passwd">]><a>&x;</a>',
    ],
)
def test_external_id_option_still_refuses_internal_subsets_and_entities(doc):
    with pytest.raises(XmlForbidden):
        _ext(doc)


def test_external_id_option_refuses_external_entity_reference_without_a_declaration():
    # No internal subset to declare it in, so a reference is just undeclared: malformed or forbidden, never expanded.
    with pytest.raises(XmlForbidden):
        _ext(_SYS + b"<a>&xxe;</a>")


def test_external_id_option_refuses_billion_laughs_quickly():
    laughs = (
        b'<!DOCTYPE lolz SYSTEM "x.dtd" ['
        b'<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
        b"]><lolz>&lol3;</lolz>"
    )
    start = time.perf_counter()
    with pytest.raises(XmlForbidden):
        _ext(laughs)
    assert time.perf_counter() - start < 1.0


def test_external_id_option_keeps_the_other_refusals():
    with pytest.raises(XmlForbidden):
        _ext(_SYS + b"<?pi x?><a/>")
    with pytest.raises(XmlForbidden):
        _ext(b'<?xml version="1.0" encoding="latin-1"?>' + _SYS + b"<a/>")
    with pytest.raises(XmlRefused):
        _ext(_SYS + b"<a/>" * 1 + b"<b/>")


def test_importing_xmlsafe_does_not_load_the_upnp_modules():
    code = (
        "import sys, devicespy.xmlsafe\n"
        "bad = [m for m in sys.modules if m.startswith('devicespy.') and m != 'devicespy.xmlsafe']\n"
        "assert not bad, bad\n"
        "import devicespy\n"
        "assert devicespy.parse is devicespy.xmlsafe.parse\n"
        "assert 'devicespy.advertise' not in sys.modules\n"
        "devicespy.announce\n"
        "assert 'devicespy.advertise' in sys.modules\n"
        "try:\n"
        "    devicespy.nonesuch\n"
        "except AttributeError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('no AttributeError')\n"
    )
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)  # noqa: S603
    assert done.returncode == 0, done.stderr
