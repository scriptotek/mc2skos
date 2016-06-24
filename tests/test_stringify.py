# encoding=utf-8
import unittest
import pytest
from lxml import etree
from mc2skos.mc2skos import Element


class TestStringify(unittest.TestCase):

    def setUp(self):
        pass

    def testSeeNote(self):
        elem = Element(etree.fromstring(u"""
            <datafield tag="253" ind1="0" ind2=" " xmlns="http://www.loc.gov/MARC21/slim">
                <subfield code="t">Vitenskap og lærdom</subfield>
                <subfield code="i">, se</subfield>
                <subfield code="a">001.2</subfield>
                <subfield code="9">ess=nse</subfield>
            </datafield>
        """))
        assert elem.stringify() == u'Vitenskap og lærdom, se 001.2'

    def testSeeAlsoNote(self):
        elem = Element(etree.fromstring(u"""
            <datafield tag="353" ind1=" " ind2=" " xmlns="http://www.loc.gov/MARC21/slim">
                <subfield code="i">Se også</subfield>
                <subfield code="a">900</subfield>
                <subfield code="i">for en</subfield>
                <subfield code="t">bred beskrivelse av situasjon og vilkår for intellektuell virksomhet</subfield>
                <subfield code="9">ess=nsa</subfield>
            </datafield>
        """))
        assert elem.stringify() == u'Se også 900 for en bred beskrivelse av situasjon og vilkår for intellektuell virksomhet'

    def testNoteWithClassNumberRange(self):
        elem = Element(etree.fromstring(u"""
            <datafield tag="253" ind1="2" ind2=" " xmlns="http://www.loc.gov/MARC21/slim">
                <subfield code="i">Klassifiser</subfield>
                <subfield code="t">andre bestemte internasjonale språk</subfield>
                <subfield code="i">med språket i</subfield>
                <subfield code="a">420</subfield>
                <subfield code="c">490</subfield>
                <subfield code="i">, f.eks.</subfield>
                <subfield code="t">latin som et diplomatspråk</subfield>
                <subfield code="e">470</subfield>
                <subfield code="i">,</subfield>
                <subfield code="t">swahili som et lingua franca</subfield>
                <subfield code="e">496.392</subfield>
                <subfield code="9">ess=ncw</subfield>
            </datafield>
        """))
        assert elem.stringify() == u'Klassifiser andre bestemte internasjonale språk med språket i 420-490, f.eks. latin som et diplomatspråk, swahili som et lingua franca'

    def testComplexNote(self):
        elem = Element(etree.fromstring(u"""
            <datafield tag="680" ind1="0" ind2=" " xmlns="http://www.loc.gov/MARC21/slim">
                <subfield code="i">Inkluderer:</subfield>
                <subfield code="t">Case-studier</subfield>
                <subfield code="i">[tidligere</subfield>
                <subfield code="x">001.432</subfield>
                <subfield code="i">];</subfield>
                <subfield code="t">utvalgsteknikker</subfield>
                <subfield code="i">;</subfield>
                <subfield code="t">rundspørringer</subfield>
                <subfield code="i">,</subfield>
                <subfield code="t">spørreskjemaer</subfield>
                <subfield code="i">,</subfield>
                <subfield code="t">feltarbeid</subfield>
                <subfield code="i">,</subfield>
                <subfield code="t">deltakende observasjon</subfield>
                <subfield code="i">,</subfield>
                <subfield code="t">intervjuer</subfield>
                <subfield code="9">ess=nin</subfield>
            </datafield>
        """))
        assert elem.stringify() == u'Inkluderer: Case-studier [tidligere 001.432]; utvalgsteknikker; rundspørringer, spørreskjemaer, feltarbeid, deltakende observasjon, intervjuer'


if __name__ == '__main__':
    unittest.main()
