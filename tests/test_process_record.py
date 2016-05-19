# encoding=utf-8
import unittest
import pytest
from lxml import etree
from mc2skos.mc2skos import process_record, Record, Constants, InvalidRecordError
from rdflib.namespace import RDF, SKOS, Namespace
from rdflib import URIRef, Literal, Graph


class TestRecord(unittest.TestCase):

    def testSimpleNumber(self):
        rec = Record(etree.fromstring('''
            <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
              <mx:leader>00000nw  a2200000n  4500</mx:leader>
              <mx:controlfield tag="008">091203aaaaaaaa</mx:controlfield>
              <mx:datafield tag="153" ind2=" " ind1=" ">
                <mx:subfield code="a">152</mx:subfield>
                <mx:subfield code="e">152</mx:subfield>
                <mx:subfield code="f">158</mx:subfield>
                <mx:subfield code="j">Sansing, bevegelse, emosjoner, fysiologiske drifter</mx:subfield>
                <mx:subfield code="9">ess=en</mx:subfield>
                <mx:subfield code="9">ess=eh</mx:subfield>
              </mx:datafield>
            </mx:record>
        '''))

        assert rec.record_type == Constants.SCHEDULE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is True
        assert rec.synthesized is False

    def testAddTableNumber(self):
        rec = Record(etree.fromstring('''
            <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:leader>00000nw  a2200000n  4500</mx:leader>
                <mx:controlfield tag="008">100414baabaaaa</mx:controlfield>
                <mx:datafield tag="153" ind2=" " ind1=" ">
                    <mx:subfield code="a">811</mx:subfield>
                    <mx:subfield code="c">818</mx:subfield>
                    <mx:subfield code="y">2</mx:subfield>
                    <mx:subfield code="a">4</mx:subfield>
                    <mx:subfield code="e">811</mx:subfield>
                    <mx:subfield code="f">818</mx:subfield>
                    <mx:subfield code="j">1867-1899 i Canada</mx:subfield>
                    <mx:subfield code="9">ess=reb</mx:subfield>
                    <mx:subfield code="9">ess=rhb</mx:subfield>
                </mx:datafield>
            </mx:record>
        '''))

        assert rec.record_type == Constants.TABLE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is True
        assert rec.synthesized is False
        assert rec.notation == '811-818:2;4'
        assert rec.parent_notation == '811-818'

    def testHistoricalAddTableNumber(self):
        rec = Record(etree.fromstring('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
            <mx:leader>00000nw  a2200000n  4500</mx:leader>
            <mx:controlfield tag="008">091203baaaaaah</mx:controlfield>
            <mx:datafield tag="153" ind2=" " ind1=" ">
                <mx:subfield code="a">820.1</mx:subfield>
                <mx:subfield code="c">828</mx:subfield>
                <mx:subfield code="y">1</mx:subfield>
                <mx:subfield code="a">7</mx:subfield>
                <mx:subfield code="e">820</mx:subfield>
                <mx:subfield code="j">1800-1837</mx:subfield>
                <mx:subfield code="9">ess=reb</mx:subfield>
                <mx:subfield code="9">ess=rhb</mx:subfield>
            </mx:datafield>
        </mx:record>
        '''))

        assert rec.record_type == Constants.TABLE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is False
        assert rec.synthesized is False

    def testSynthesizedNumberSpan(self):
        rec = Record(etree.fromstring('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="008">091203abdaaaba</mx:controlfield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">133.01</mx:subfield>
            <mx:subfield code="c">133.09</mx:subfield>
            <mx:subfield code="e">133</mx:subfield>
            <mx:subfield code="j">Generell forminndeling</mx:subfield>
            <mx:subfield code="9">ess=en</mx:subfield>
            <mx:subfield code="9">ess=eh</mx:subfield>
          </mx:datafield>
        </mx:record>
        '''))

        assert rec.record_type == Constants.SCHEDULE_RECORD
        assert rec.number_type == Constants.NUMBER_SPAN
        assert rec.display is True
        assert rec.synthesized is True

    def testHiddenSynthesizedScheduleRecord(self):
        rec = Record(etree.fromstring('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="008">091203aaaaaabb</mx:controlfield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">025.1712</mx:subfield>
            <mx:subfield code="e">025.17</mx:subfield>
            <mx:subfield code="9">ess=ien</mx:subfield>
          </mx:datafield>
        </mx:record>
        '''))

        assert rec.record_type == Constants.SCHEDULE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is False
        assert rec.synthesized is True


class TestProcessRecord(unittest.TestCase):

    def setUp(self):
        self.graph = Graph()
        self.nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}

    def testRecordWithoutLeader(self):
        g = Graph()

        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
          </marc:record>
        ''')

        with pytest.raises(InvalidRecordError):
            process_record(g, rec)

    def testRecordWithInvalidLeader(self):
        g = Graph()

        # A Marc21 Authority record
        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nz  a2200000n  4500</marc:leader>
          </marc:record>
        ''')

        with pytest.raises(InvalidRecordError):
            process_record(g, rec)

    def testRecordWithout153(self):
        # Not sure if this test should fail or not.
        g = Graph()

        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
          </marc:record>
        ''')

        with pytest.raises(InvalidRecordError):
            process_record(g, rec)

    def test153(self):
        rec = etree.fromstring('''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
            <marc:datafield tag="153" ind1=" " ind2=" ">
              <marc:subfield code="a">003.5</marc:subfield>
              <marc:subfield code="e">003</marc:subfield>
              <marc:subfield code="h">Generalities</marc:subfield>
              <marc:subfield code="h">Systems</marc:subfield>
              <marc:subfield code="j">Theory of communication and control</marc:subfield>
            </marc:datafield>
          </marc:record>
        ''')
        graph = Graph()
        process_record(graph, rec, base_uri='http://test/{object}')
        uri = URIRef(u'http://test/003.5')

        assert set(graph) == set([
            (uri, RDF.type, SKOS.Concept),
            (uri, SKOS.broader, URIRef(u'http://test/003')),
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
        process_record(graph, rec, base_uri='http://test/{object}')
        uri = URIRef(u'http://test/564.58')

        assert graph.preferredLabel(uri)[0][0] == SKOS.prefLabel
        assert graph.preferredLabel(uri)[0][1].language == 'nb'

if __name__ == '__main__':
    unittest.main()
