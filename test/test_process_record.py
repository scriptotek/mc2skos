# encoding=utf-8
import unittest
import pytest
from lxml import etree
from mc2skos.mc2skos import process_record, ClassificationRecord, Constants, InvalidRecordError
from rdflib.namespace import RDF, SKOS, Namespace
from rdflib import URIRef, Literal, Graph, BNode


class TestClassificationRecord(unittest.TestCase):

    def testSimpleNumber(self):
        rec = ClassificationRecord('''
            <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
              <mx:leader>00000nw  a2200000n  4500</mx:leader>
              <mx:controlfield tag="008">091203aaaaaaaa</mx:controlfield>
              <mx:datafield tag="084" ind2=" " ind1="0">
                <mx:subfield code="a">ddc</mx:subfield>
                <mx:subfield code="c">23no</mx:subfield>
                <mx:subfield code="e">nob</mx:subfield>
              </mx:datafield>
              <mx:datafield tag="153" ind2=" " ind1=" ">
                <mx:subfield code="a">152</mx:subfield>
                <mx:subfield code="e">152</mx:subfield>
                <mx:subfield code="f">158</mx:subfield>
                <mx:subfield code="j">Sansing, bevegelse, emosjoner, fysiologiske drifter</mx:subfield>
                <mx:subfield code="9">ess=en</mx:subfield>
                <mx:subfield code="9">ess=eh</mx:subfield>
              </mx:datafield>
            </mx:record>
        ''')

        assert rec.record_type == Constants.SCHEDULE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is True
        assert rec.synthesized is False

    def testAddTableNumber(self):
        rec = ClassificationRecord('''
            <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:leader>00000nw  a2200000n  4500</mx:leader>
                <mx:controlfield tag="008">100414baabaaaa</mx:controlfield>
                <mx:datafield tag="084" ind2=" " ind1="0">
                    <mx:subfield code="a">ddc</mx:subfield>
                    <mx:subfield code="c">23no</mx:subfield>
                </mx:datafield>
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
        ''')

        assert rec.record_type == Constants.TABLE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is True
        assert rec.synthesized is False
        assert rec.notation == '811-818:2;4'
        assert len(rec.relations) == 1
        assert rec.relations[0]['uri'] == 'http://dewey.info/class/811-818/e23/'
        assert rec.relations[0]['relation'] == SKOS.broader

    def testHistoricalAddTableNumber(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
            <mx:leader>00000nw  a2200000n  4500</mx:leader>
            <mx:controlfield tag="008">091203baaaaaah</mx:controlfield>
            <mx:datafield tag="084" ind2=" " ind1="0">
                <mx:subfield code="a">ddc</mx:subfield>
                <mx:subfield code="c">23no</mx:subfield>
                <mx:subfield code="e">nob</mx:subfield>
            </mx:datafield>
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
        ''')

        assert rec.record_type == Constants.TABLE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is False
        assert rec.synthesized is False

    def testSynthesizedNumberSpan(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="008">091203abdaaaba</mx:controlfield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
            <mx:subfield code="e">nob</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">133.01</mx:subfield>
            <mx:subfield code="c">133.09</mx:subfield>
            <mx:subfield code="e">133</mx:subfield>
            <mx:subfield code="j">Generell forminndeling</mx:subfield>
            <mx:subfield code="9">ess=en</mx:subfield>
            <mx:subfield code="9">ess=eh</mx:subfield>
          </mx:datafield>
        </mx:record>
        ''')

        assert rec.record_type == Constants.SCHEDULE_RECORD
        assert rec.number_type == Constants.NUMBER_SPAN
        assert rec.display is True
        assert rec.synthesized is True

    def testSynthesizedScheduleRecord(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="008">091203aaaaaabb</mx:controlfield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
            <mx:subfield code="e">nob</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">025.1712</mx:subfield>
            <mx:subfield code="e">025.17</mx:subfield>
            <mx:subfield code="9">ess=ien</mx:subfield>
          </mx:datafield>
        </mx:record>
        ''')

        assert rec.record_type == Constants.SCHEDULE_RECORD
        assert rec.number_type == Constants.SINGLE_NUMBER
        assert rec.display is True
        assert rec.synthesized is True

    def testSynthesizedNumberComponents1(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="001">ocd00132963</mx:controlfield>
          <mx:controlfield tag="008">100204aaaaaabb</mx:controlfield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
            <mx:subfield code="e">nob</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">306.6804</mx:subfield>
            <mx:subfield code="e">306.63</mx:subfield>
            <mx:subfield code="f">306.69</mx:subfield>
            <mx:subfield code="9">ess=ien</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="765" ind2=" " ind1="0">
              <mx:subfield code="b">306.6</mx:subfield>
              <mx:subfield code="a">306.63</mx:subfield>
              <mx:subfield code="c">306.69</mx:subfield>
              <mx:subfield code="r">2</mx:subfield>
              <mx:subfield code="s">804</mx:subfield>
              <mx:subfield code="u">306.6804</mx:subfield>
              <mx:subfield code="9">ess=hn</mx:subfield>
            </mx:datafield>
        </mx:record>
        ''')

        assert rec.components == ['306.6', '280.4']

    def testSynthesizedNumberComponents2(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="001">ocd00123528</mx:controlfield>
          <mx:controlfield tag="008">091203aaaaaabb</mx:controlfield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
            <mx:subfield code="e">nob</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">299.3113</mx:subfield>
            <mx:subfield code="e">299.31</mx:subfield>
            <mx:subfield code="9">ess=ien</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="765" ind2=" " ind1="0">
              <mx:subfield code="b">299.31</mx:subfield>
              <mx:subfield code="a">299.31</mx:subfield>
              <mx:subfield code="a">290</mx:subfield>
              <mx:subfield code="w">290</mx:subfield>
              <mx:subfield code="y">1</mx:subfield>
              <mx:subfield code="a">1</mx:subfield>
              <mx:subfield code="c">9</mx:subfield>
              <mx:subfield code="r">20</mx:subfield>
              <mx:subfield code="s">13</mx:subfield>
              <mx:subfield code="u">299.3113</mx:subfield>
            </mx:datafield>
            <mx:datafield tag="765" ind2=" " ind1="0">
              <mx:subfield code="b">299</mx:subfield>
              <mx:subfield code="a">299.1</mx:subfield>
              <mx:subfield code="c">299.4</mx:subfield>
              <mx:subfield code="z">5</mx:subfield>
              <mx:subfield code="r">9</mx:subfield>
              <mx:subfield code="s">31</mx:subfield>
              <mx:subfield code="u">299.31</mx:subfield>
            </mx:datafield>
        </mx:record>
        ''')

        assert rec.components == ['299', '5--931', '201.3']

    @pytest.mark.skip(reason="add table numbers not yet supported")
    def testSynthesizedNumberComponentsIncludingAddTable(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="001">ocd00117858</mx:controlfield>
          <mx:controlfield tag="003">OCoLC-D</mx:controlfield>
          <mx:controlfield tag="005">20150910004647.0</mx:controlfield>
          <mx:controlfield tag="008">091203aaaaaabb</mx:controlfield>
          <mx:datafield tag="040" ind2=" " ind1=" ">
            <mx:subfield code="a">OCLCD</mx:subfield>
            <mx:subfield code="b">nob</mx:subfield>
            <mx:subfield code="c">OCLCD</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
            <mx:subfield code="e">nob</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">032.020993</mx:subfield>
            <mx:subfield code="e">032.02</mx:subfield>
            <mx:subfield code="9">ess=ien</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="765" ind2=" " ind1="0">
            <mx:subfield code="b">032.0209</mx:subfield>
            <mx:subfield code="z">1</mx:subfield>
            <mx:subfield code="a">093</mx:subfield>
            <mx:subfield code="c">099</mx:subfield>
            <mx:subfield code="z">2</mx:subfield>
            <mx:subfield code="s">93</mx:subfield>
            <mx:subfield code="u">032.020993</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="765" ind2=" " ind1="0">
            <mx:subfield code="b">032.02</mx:subfield>
            <mx:subfield code="z">1</mx:subfield>
            <mx:subfield code="s">09</mx:subfield>
            <mx:subfield code="u">032.0209</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="765" ind2=" " ind1="0">
            <mx:subfield code="b">032</mx:subfield>
            <mx:subfield code="a">032</mx:subfield>
            <mx:subfield code="a">031</mx:subfield>
            <mx:subfield code="c">039</mx:subfield>
            <mx:subfield code="w">031</mx:subfield>
            <mx:subfield code="c">039</mx:subfield>
            <mx:subfield code="y">1</mx:subfield>
            <mx:subfield code="t">02</mx:subfield>
            <mx:subfield code="u">032.02</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="750" ind2="7" ind1=" ">
            <mx:subfield code="a">Engelske almanakker</mx:subfield>
            <mx:subfield code="z">New Zealand</mx:subfield>
            <mx:subfield code="0">(OCoLC-D)792f96bb-142c-43c6-a20e-ed5ed2088388</mx:subfield>
            <mx:subfield code="2">ddcri</mx:subfield>
            <mx:subfield code="9">ps=EO</mx:subfield>
          </mx:datafield>
        </mx:record>
        ''')

        assert rec.components == ['032', '031-039:02', '1--09', '2--93']

    def testIndexTerms(self):
        rec = ClassificationRecord('''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="001">ocd00146759</mx:controlfield>
          <mx:controlfield tag="008">100204aaaaaaaa</mx:controlfield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
            <mx:subfield code="e">nob</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">543.17</mx:subfield>
            <mx:subfield code="e">543.1</mx:subfield>
            <mx:subfield code="j">Analytisk organisk kjemi</mx:subfield>
            <mx:subfield code="9">ess=en</mx:subfield>
            <mx:subfield code="9">ess=eh</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="750" ind2="7" ind1=" ">
            <mx:subfield code="a">Analytisk kjemi</mx:subfield>
            <mx:subfield code="x">organisk kjemi</mx:subfield>
            <mx:subfield code="0">(OCoLC-D)8c2057ce-4544-4593-9699-1008a7dcd4ef</mx:subfield>
            <mx:subfield code="2">ddcri</mx:subfield>
            <mx:subfield code="9">ps=PE</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="750" ind2="7" ind1=" ">
            <mx:subfield code="a">Kjemisk analyse</mx:subfield>
            <mx:subfield code="x">organisk kjemi</mx:subfield>
            <mx:subfield code="0">(OCoLC-D)934d9916-e069-4351-994f-44b4c02f2f4d</mx:subfield>
            <mx:subfield code="2">ddcri</mx:subfield>
            <mx:subfield code="9">ps=PE</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="750" ind2="7" ind1=" ">
            <mx:subfield code="a">Organisk kjemi</mx:subfield>
            <mx:subfield code="x">analytisk kjemi</mx:subfield>
            <mx:subfield code="0">(OCoLC-D)9d92b5a2-7f96-4db7-a212-19c40edf7a93</mx:subfield>
            <mx:subfield code="2">ddcri</mx:subfield>
            <mx:subfield code="9">ps=PE</mx:subfield>
          </mx:datafield>
        </mx:record>
        ''')

        assert rec.altLabel == [
            {'term': 'Analytisk kjemi--organisk kjemi'},
            {'term': 'Kjemisk analyse--organisk kjemi'},
            {'term': 'Organisk kjemi--analytisk kjemi'}]


class TestProcessRecord(unittest.TestCase):

    def setUp(self):
        self.graph = Graph()
        self.nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}

    def testEmptyRecord(self):
        g = Graph()

        rec = '''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
          </marc:record>
        '''

        with pytest.raises(InvalidRecordError):
            process_record(g, rec)

    def testRecordWithInvalidLeader(self):

        # A Marc21 Bibliographic record
        rec = '''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000aa  a2200000n  4500</marc:leader>
            <marc:datafield tag="084" ind2=" " ind1="0">
              <marc:subfield code="a">ddc</marc:subfield>
              <marc:subfield code="c">23no</marc:subfield>
              <marc:subfield code="e">nob</marc:subfield>
            </marc:datafield>
          </marc:record>
        '''

        with pytest.raises(InvalidRecordError):
            process_record(Graph(), rec)

    def testRecordWithout153(self):
        # Not sure if this test should fail or not.

        rec = '''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
            <marc:datafield tag="084" ind2=" " ind1="0">
              <marc:subfield code="a">ddc</marc:subfield>
              <marc:subfield code="c">23no</marc:subfield>
              <marc:subfield code="e">nob</marc:subfield>
            </marc:datafield>
          </marc:record>
        '''

        with pytest.raises(InvalidRecordError):
            process_record(Graph(), rec)

    def test153(self):
        rec = '''
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
        '''
        graph = Graph()
        process_record(graph, rec, base_uri='http://test/{object}')
        uri = URIRef(u'http://test/003.5')

        assert set(graph) == set([
            (uri, RDF.type, SKOS.Concept),
            (uri, SKOS.broader, URIRef(u'http://test/003')),
            (uri, SKOS.prefLabel, Literal('Theory of communication and control', lang='en')),
            (uri, SKOS.inScheme, URIRef(u'http://test/')),
            (uri, SKOS.notation, Literal('003.5')),
        ])

    def test_language(self):
        rec = '''
          <marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">
            <marc:leader>00000nw  a2200000n  4500</marc:leader>
            <marc:datafield tag="040" ind2=" " ind1=" ">
              <marc:subfield code="a">OCLCD</marc:subfield>
              <marc:subfield code="b">nob</marc:subfield>
              <marc:subfield code="c">OCLCD</marc:subfield>
            </marc:datafield>
            <marc:datafield tag="084" ind2=" " ind1="0">
              <marc:subfield code="a">ddc</marc:subfield>
              <marc:subfield code="c">23no</marc:subfield>
              <marc:subfield code="e">nob</marc:subfield>
            </marc:datafield>
            <marc:datafield tag="153" ind2=" " ind1=" ">
              <marc:subfield code="a">564.58</marc:subfield>
              <marc:subfield code="e">564.5</marc:subfield>
              <marc:subfield code="j">Decapoda (tiarmede blekkspruter)</marc:subfield>
            </marc:datafield>
          </marc:record>
        '''
        graph = Graph()
        process_record(graph, rec, base_uri='http://test/{object}')
        uri = URIRef(u'http://test/564.58')

        assert graph.preferredLabel(uri)[0][0] == SKOS.prefLabel
        assert graph.preferredLabel(uri)[0][1].language == 'nb'

    def testSynthesizedNumberComponents(self):
        rec = '''
        <mx:record xmlns:mx="http://www.loc.gov/MARC21/slim">
          <mx:leader>00000nw  a2200000n  4500</mx:leader>
          <mx:controlfield tag="001">ocd00132963</mx:controlfield>
          <mx:controlfield tag="008">100204aaaaaabb</mx:controlfield>
          <mx:datafield tag="084" ind2=" " ind1="0">
            <mx:subfield code="a">ddc</mx:subfield>
            <mx:subfield code="c">23no</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="153" ind2=" " ind1=" ">
            <mx:subfield code="a">306.6804</mx:subfield>
            <mx:subfield code="e">306.63</mx:subfield>
            <mx:subfield code="f">306.69</mx:subfield>
            <mx:subfield code="9">ess=ien</mx:subfield>
          </mx:datafield>
          <mx:datafield tag="765" ind2=" " ind1="0">
            <mx:subfield code="b">306.6</mx:subfield>
            <mx:subfield code="a">306.63</mx:subfield>
            <mx:subfield code="c">306.69</mx:subfield>
            <mx:subfield code="r">2</mx:subfield>
            <mx:subfield code="s">804</mx:subfield>
            <mx:subfield code="u">306.6804</mx:subfield>
            <mx:subfield code="9">ess=hn</mx:subfield>
          </mx:datafield>
        </mx:record>
        '''

        graph = Graph()
        process_record(graph, rec, include_components=True)

        components = [n[0] for n in graph.query('''
            PREFIX mads: <http://www.loc.gov/mads/rdf/v1#>
            SELECT ?comp WHERE {
              <http://dewey.info/class/306.6804/e23/> mads:componentList/rdf:rest*/rdf:first ?comp
            }
        ''')]

        assert len(components) == 2
        assert components == [URIRef(u'http://dewey.info/class/306.6/e23/'),
                              URIRef(u'http://dewey.info/class/280.4/e23/')]


if __name__ == '__main__':
    unittest.main()
