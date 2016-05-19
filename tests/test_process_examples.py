# encoding=utf-8
import unittest
import pytest
import os
import glob
import re
from lxml import etree
from mc2skos.mc2skos import process_record
from rdflib.namespace import RDF, SKOS, Namespace
from rdflib import URIRef, Literal, Graph


def get_records(filename):
    for _, record in etree.iterparse(filename, tag='{http://www.loc.gov/MARC21/slim}record'):
        yield record
        record.clear()


@pytest.fixture(params=glob.glob('examples/*.xml'))
def marc_file(request):
    return request.param


def test_example(marc_file):

    graph = Graph()
    nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}
    ns = Namespace('http://test/')

    print(marc_file)
    match = re.match('^(?P<name>examples/(?P<scheme>[a-z]+\d{2})(?P<lang>[a-z]+)-(?P<notation>((?P<table>\d+)--)?[\d.]+-?[\d.]*))\.xml$', marc_file)
    assert match is not None

    name = match.group('name')
    notation = match.group('notation')
    table = match.group('table')

    rdf_file = marc_file[:marc_file.rindex('.')] + '.ttl'

    graph = Graph()
    for record in get_records(marc_file):
        process_record(graph, record, nsmap, ns, None, None)

    expect = Graph()
    uri = URIRef(u'http://test/' + notation)
    expect.add((uri, RDF.type, SKOS.Concept))
    if table:
        notation = "T" + notation
    expect.add((uri, SKOS.notation, Literal(notation)))

    if os.path.isfile(rdf_file):
        expect.parse(rdf_file, format='turtle')
    elif len(graph) > 0:
        graph.namespace_manager.bind('skos', URIRef('http://www.w3.org/2004/02/skos/core#'))
        graph.serialize(destination=rdf_file, format='turtle')

    for triple in expect:
        assert triple in graph

if __name__ == '__main__':
    unittest.main()
