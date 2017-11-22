# encoding=utf-8
import unittest
import pytest
import os
import sys
import glob
import re
from lxml import etree
from mc2skos.reader import MarcFileReader
from mc2skos.mc2skos import process_records
from rdflib.namespace import RDF, SKOS, OWL, DCTERMS, Namespace
from rdflib import URIRef, Literal, Graph


def examples(pattern):
    pattern = '^(examples/%s)\.xml$' % (pattern)
    files = glob.glob('examples/*.xml')
    files = filter(lambda x: re.match(pattern, x), files)

    return [(MarcFileReader(f), re.match(pattern, f)) for f in files]


def check_processing(marc, expect, **kwargs):
    graph = process_records(marc.records(), **kwargs)
    filename = re.sub('xml$', 'ttl', marc.name)

    graph.namespace_manager.bind('skos', SKOS)
    graph.namespace_manager.bind('owl', OWL)
    graph.namespace_manager.bind('dcterms', DCTERMS)

    if os.path.isfile(filename):
        expect.parse(filename, format='turtle')
    elif len(graph) > 0:
        graph.serialize(destination=filename, format='turtle')

    # graph.serialize(destination=sys.stdout, format='turtle')

    for triple in expect:
        assert triple in graph


@pytest.mark.parametrize('marc,match',
                         examples('ddc(?P<edition>\d{2})(?P<lang>[a-z]+)-'
                                  '(?P<notation>((?P<table>\d+)--)?[\d.]+-?[\d.]*)'))
def test_ddc_example(marc, match):
    edition = match.group('edition')
    notation = match.group('notation')
    table = match.group('table')

    expect = Graph()
    uri = URIRef(u'http://dewey.info/class/' + notation + '/e' + edition + '/')
    expect.add((uri, RDF.type, SKOS.Concept))
    if table:
        notation = "T" + notation
    expect.add((uri, SKOS.notation, Literal(notation)))

    check_processing(marc, expect, include_webdewey=True)


@pytest.mark.parametrize('marc,match',
                         examples('(?P<scheme>bk|asb)-(?P<notation>[0-9.]+)'))
def test_bk_asb_example(marc, match):
    scheme = match.group('scheme')
    notation = match.group('notation')

    expect = Graph()
    uri = URIRef(u'http://uri.gbv.de/terminology/{}/{}'.format(scheme, notation))
    expect.add((uri, RDF.type, SKOS.Concept))

    check_processing(marc, expect, include_altlabels=True)


@pytest.mark.parametrize('marc,match', examples('rvk'))
def test_rvk_example(marc, match):

    options = {
        'include_altlabels': True,
        'scheme_uri': 'http://example.org/rvk',
        'base_uri': 'http://example.org/rvk/{object}'
    }

    check_processing(marc, Graph(), **options)

vocabularies = {
    'lcsh': 'http://id.loc.gov/authorities/subjects/',
    'noubomn': 'http://data.ub.uio.no/realfagstermer/',
    'noubojur': 'http://data.ub.uio.no/lskjema/',
    'humord': 'http://data.ub.uio.no/humord/',
    'nalt': 'http://lod.nal.usda.gov/nalt/',
}


@pytest.mark.parametrize('marc,match',
                         examples('(?P<vocabulary>' + '|'.join(vocabularies.keys()) + ')-(?P<control_number>.+)'))
def test_authority_example(marc, match):
    vocabulary = match.group('vocabulary')
    control_number = match.group('control_number')

    uri_base = vocabularies[vocabulary]

    expect = Graph()
    uri = URIRef(uri_base + control_number)
    expect.add((uri, RDF.type, SKOS.Concept))

    check_processing(marc, expect, include_altlabels=True)

if __name__ == '__main__':
    unittest.main()
