# encoding=utf-8
import unittest
import pytest
import os
import re
from lxml import etree
from mc2skos.mc2skos import process_record
from rdflib.namespace import RDF, SKOS, Namespace
from rdflib import URIRef, Literal, Graph


def get_records(marcfile):
    for _, record in etree.iterparse(marcfile, tag='{http://www.loc.gov/MARC21/slim}record'):
        yield record
        record.clear()


class TestProcessExamples(unittest.TestCase):

    def setUp(self):
        self.graph = Graph()
        self.nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}
        self.ns = Namespace('http://test/')

    def testExamples(self):
        pattern = re.compile('^(ddc([0-9][0-9])([a-z]+)-([0-9.]+|([0-9])--([0-9.]+)))\.xml$')

        for marcfile in os.listdir('examples'):
            match = pattern.match(marcfile)
            if not match:
                continue

            name = match.group(1)
            notation = match.group(4)
            table = match.group(5)

            marcfile = 'examples/' + marcfile
            # print marcfile
            rdffile = 'examples/' + name + '.ttl'

            graph = Graph()
            for record in get_records(marcfile):
                process_record(graph, record, self.nsmap, self.ns, None, None)
            # print graph.serialize(format='turtle')

            expect = Graph()
            uri = URIRef(u'http://test/' + notation)
            expect.add((uri, RDF.type, SKOS.Concept))
            if table:
                notation = "T" + notation
            expect.add((uri, SKOS.notation, Literal(notation)))

            if os.path.isfile(rdffile):
                expect.parse(rdffile, format='turtle')
            else:
                if len(graph) > 0:
                    graph.namespace_manager.bind('skos', URIRef('http://www.w3.org/2004/02/skos/core#'))
                    graph.serialize(destination=rdffile, format='turtle')

            for triple in expect:
                assert triple in graph

if __name__ == '__main__':
    unittest.main()
