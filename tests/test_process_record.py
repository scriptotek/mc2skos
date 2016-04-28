# encoding=utf-8
import unittest
import pytest
from lxml import etree
from mc2skos.mc2skos import process_record, InvalidRecordError
from rdflib.namespace import RDF, SKOS, Namespace
from rdflib import URIRef, Literal, Graph


class TestProcessRecord(unittest.TestCase):

    def setUp(self):
        self.graph = Graph()
        self.nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}
        self.ns = Namespace('http://test/')

    def testRecordWithoutLeader(self):
        g = Graph()

        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
          </marc:record>
        ''')

        with pytest.raises(InvalidRecordError):
            process_record(g, rec, self.nsmap, self.ns, None, None)

    def testRecordWithInvalidLeader(self):
        g = Graph()

        # A Marc21 Authority record
        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nz  a2200000n  4500</marc:leader>
          </marc:record>
        ''')

        with pytest.raises(InvalidRecordError):
            process_record(g, rec, self.nsmap, self.ns, None, None)

    def testMinimalRecord(self):
        g = Graph()

        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
          </marc:record>
        ''')

        process_record(g, rec, self.nsmap, self.ns, None, None)

        assert len(g) == 0

    def test153(self):
        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
            <marc:datafield tag="153" ind1=" " ind2=" ">
              <marc:subfield code="a">003.5</marc:subfield>
              <marc:subfield code="h">Generalities</marc:subfield>
              <marc:subfield code="h">Systems</marc:subfield>
              <marc:subfield code="j">Theory of communication and control</marc:subfield>
            </marc:datafield>
          </marc:record>
        ''')
        graph = Graph()
        process_record(graph, rec, self.nsmap, self.ns, None, None)
        uri = URIRef(u'http://test/003.5')

        assert set(graph) == set([
            (uri, RDF.type, SKOS.Concept),
            (uri, SKOS.prefLabel, Literal('Theory of communication and control', lang='en')),
            (uri, SKOS.notation, Literal('003.5')),
        ])

    def test_language(self):
        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
            <marc:datafield tag="040" ind2=" " ind1=" ">
              <marc:subfield code="a">OCLCD</marc:subfield>
              <marc:subfield code="b">nob</marc:subfield>
              <marc:subfield code="c">OCLCD</marc:subfield>
            </marc:datafield>
            <marc:datafield tag="153" ind2=" " ind1=" ">
              <marc:subfield code="a">564.58</marc:subfield>
              <marc:subfield code="e">564.5</marc:subfield>
              <marc:subfield code="j">Decapoda (tiarmede blekkspruter)</marc:subfield>
            </marc:datafield>
          </marc:record>
        ''')
        graph = Graph()
        process_record(graph, rec, self.nsmap, self.ns, None, None)
        uri = URIRef(u'http://test/564.58')

        assert graph.preferredLabel(uri)[0][0] == SKOS.prefLabel
        assert graph.preferredLabel(uri)[0][1].language == 'nb'

if __name__ == '__main__':
    unittest.main()
