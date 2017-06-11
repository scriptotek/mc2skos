# encoding=utf-8
import unittest
import pytest
import os
import sys
import glob
import re
from lxml import etree
from mc2skos.mc2skos import process_record
from rdflib.namespace import RDF, SKOS, OWL, DCTERMS, Namespace
from rdflib import URIRef, Literal, Graph


class MarcFile:
    record_tag = '{http://www.loc.gov/MARC21/slim}record'

    def __init__(self, name):
        self.name = name

    def records(self):
        for _, record in etree.iterparse(self.name, tag=MarcFile.record_tag):
            yield record
            record.clear()

    def processed_records(self, **options):
        graph = Graph()
        for record in self.records():
            process_record(graph, record, **options)
        return graph


def examples(prefix, pattern):

    pattern = '^(examples/%s%s)\.xml$' % (prefix, pattern)
    files = glob.glob('examples/%s*.xml' % prefix)

    return [(MarcFile(f), re.match(pattern, f)) for f in files]


def check_rdf(graph, expect, rdf_file):
    graph.namespace_manager.bind('skos', SKOS)
    graph.namespace_manager.bind('dcterms', DCTERMS)
    graph.namespace_manager.bind('owl', OWL)

    if os.path.isfile(rdf_file):
        expect.parse(rdf_file, format='turtle')
    elif len(graph) > 0:
        graph.serialize(destination=rdf_file, format='turtle')

    # graph.serialize(destination=sys.stdout, format='turtle')

    for triple in expect:
        assert triple in graph


@pytest.mark.parametrize('marc_file',
                         examples('ddc',
                                  '(?P<edition>\d{2})(?P<lang>[a-z]+)-'
                                  '(?P<notation>((?P<table>\d+)--)?[\d.]+-?[\d.]*)'))
def test_ddc_example(marc_file):
    marc, match = tuple(marc_file)

    edition = match.group('edition')
    notation = match.group('notation')
    table = match.group('table')
    rdf_file = match.group(1) + '.ttl'

    expect = Graph()
    uri = URIRef(u'http://dewey.info/class/' + notation + '/e' + edition + '/')
    expect.add((uri, RDF.type, SKOS.Concept))
    if table:
        notation = "T" + notation
    expect.add((uri, SKOS.notation, Literal(notation)))

    graph = marc.processed_records()
    check_rdf(graph, expect, rdf_file)


@pytest.mark.parametrize('marc_file', examples('bk', '-(?P<notation>[0-9.]+)'))
def test_bk_example(marc_file):
    marc, match = tuple(marc_file)

    notation = match.group('notation')
    rdf_file = match.group(1) + '.ttl'

    expect = Graph()
    uri = URIRef(u'http://uri.gbv.de/terminology/bk/' + notation)
    expect.add((uri, RDF.type, SKOS.Concept))

    graph = marc.processed_records(include_indexterms=True)
    check_rdf(graph, expect, rdf_file)


if __name__ == '__main__':
    unittest.main()
