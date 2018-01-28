# encoding=utf-8
import unittest
import pytest
from lxml import etree
from mc2skos.mc2skos import ClassificationRecord, Element


class TestParse153(unittest.TestCase):

    def testSimpleClass(self):
        element = Element('''
            <marc:datafield tag="153" ind1=" " ind2=" " xmlns:marc="http://www.loc.gov/MARC21/slim">
              <marc:subfield code="a">003.5</marc:subfield>
              <marc:subfield code="e">003</marc:subfield>
              <marc:subfield code="h">Generalities</marc:subfield>
              <marc:subfield code="h">Systems</marc:subfield>
              <marc:subfield code="j">Theory of communication and control</marc:subfield>
            </marc:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert notation == '003.5'
        assert parent_notation == '003'
        assert is_top_concept is False
        assert caption == 'Theory of communication and control'

    def testTableAddTableEntry(self):
        element = Element('''
            <mx:datafield tag="153" ind2=" " ind1=" " xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:subfield code="z">3B</mx:subfield>
                <mx:subfield code="a">81</mx:subfield>
                <mx:subfield code="c">89</mx:subfield>
                <mx:subfield code="y">1</mx:subfield>
                <mx:subfield code="a">02</mx:subfield>
                <mx:subfield code="z">3B</mx:subfield>
                <mx:subfield code="e">81</mx:subfield>
                <mx:subfield code="f">89</mx:subfield>
                <mx:subfield code="j">Anekdoter, epigrammer, graffiti, vitser, vittigheter, sitater, gåter, tungekrøllere</mx:subfield>
                <mx:subfield code="9">ess=ren</mx:subfield>
                <mx:subfield code="9">ess=reh</mx:subfield>
            </mx:datafield>

        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table == '3B'
        assert notation == '3B--81-89:02'
        assert is_top_concept is False
        assert parent_notation == '3B--81-89'
        assert caption == u'Anekdoter, epigrammer, graffiti, vitser, vittigheter, sitater, gåter, tungekrøllere'

    def testAddTableEntry(self):
        element = Element('''
            <mx:datafield tag="153" ind2=" " ind1=" " xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:subfield code="a">820.1</mx:subfield>
                <mx:subfield code="c">828</mx:subfield>
                <mx:subfield code="y">4</mx:subfield>
                <mx:subfield code="a">1</mx:subfield>
                <mx:subfield code="e">820</mx:subfield>
                <mx:subfield code="j">Early period to 1858</mx:subfield>
                <mx:subfield code="9">ess=reb</mx:subfield>
                <mx:subfield code="9">ess=rhb</mx:subfield>
            </mx:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table is None
        assert notation == '820.1-828:4;1'
        assert is_top_concept is False
        assert parent_notation == '820'
        assert caption == u'Early period to 1858'

    def testTableEntryOldStyle(self):
        element = Element('''
            <marc:datafield tag="153" ind1=" " ind2=" " xmlns:marc="http://www.loc.gov/MARC21/slim">
                <marc:subfield code="z">6</marc:subfield>
                <marc:subfield code="a">9839</marc:subfield>
                <marc:subfield code="h">Languages</marc:subfield>
                <marc:subfield code="h">Other languages</marc:subfield>
                <marc:subfield code="h">South American native languages</marc:subfield>
                <marc:subfield code="h">Quechuan (Kechuan), Aymaran, Tucanoan, Tupí, Arawakan languages</marc:subfield>
                <marc:subfield code="j">Arawakan languages</marc:subfield>
            </marc:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table == '6'
        assert notation == '6--9839'
        assert is_top_concept is False
        assert parent_notation is None
        assert caption == u'Arawakan languages'

    def testComplexTableEntryWithUndocumentStuff(self):
        # Test that none of the extra stuff (after $f) leaks into the notation
        element = Element('''
            <mx:datafield tag="153" ind2=" " ind1=" " xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:subfield code="z">1</mx:subfield>
                <mx:subfield code="a">0926</mx:subfield>
                <mx:subfield code="z">1</mx:subfield>
                <mx:subfield code="e">0923</mx:subfield>
                <mx:subfield code="f">0928</mx:subfield>
                <mx:subfield code="j">Samlingsbiografier om personer inndelt etter diverse sosiale kjennetegn</mx:subfield>
                <mx:subfield code="i">[tidligere</mx:subfield>
                <mx:subfield code="z">1</mx:subfield>
                <mx:subfield code="x">0922</mx:subfield>
                <mx:subfield code="i">,</mx:subfield>
                <mx:subfield code="z">1</mx:subfield>
                <mx:subfield code="x">0923</mx:subfield>
                <mx:subfield code="i">]</mx:subfield>
                <mx:subfield code="9">ess=ten</mx:subfield>
                <mx:subfield code="9">ess=eh</mx:subfield>
                <mx:subfield code="9">ess=nrl</mx:subfield>
              </mx:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table == '1'
        assert notation == '1--0926'
        assert is_top_concept is False
        assert parent_notation == '1--0923-0928'
        assert caption == u'Samlingsbiografier om personer inndelt etter diverse sosiale kjennetegn'

    def testStandardSubdivisionInfo(self):
        element = Element('''
            <mx:datafield tag="153" ind2=" " ind1=" " xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:subfield code="a">973</mx:subfield>
                <mx:subfield code="9">ess=si1</mx:subfield>
            </mx:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table is None
        assert notation == '973'
        assert caption is None

    def testSynthesizedNumber(self):
        element = Element('''
              <mx:datafield tag="153" ind2=" " ind1=" " xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:subfield code="a">001.4092</mx:subfield>
                <mx:subfield code="e">001.4</mx:subfield>
                <mx:subfield code="9">ess=ien</mx:subfield>
              </mx:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table is None
        assert is_top_concept is False
        assert notation == '001.4092'
        assert parent_notation == '001.4'
        assert caption is None

    def testExtraSubfields(self):
        element = Element('''
              <mx:datafield tag="153" ind2=" " ind1=" " xmlns:mx="http://www.loc.gov/MARC21/slim">
                <mx:subfield code="a">332.0240081</mx:subfield>
                <mx:subfield code="c">332.0240088</mx:subfield>
                <mx:subfield code="e">332.024001</mx:subfield>
                <mx:subfield code="f">332.024009</mx:subfield>
                <mx:subfield code="j">Miscellaneous specific kinds of persons</mx:subfield>
                <mx:subfield code="i">[formerly</mx:subfield>
                <mx:subfield code="x">332.02404</mx:subfield>
                <mx:subfield code="c">332.0249</mx:subfield>
                <mx:subfield code="i">]</mx:subfield>
                <mx:subfield code="9">ess=en</mx:subfield>
                <mx:subfield code="9">ess=eh</mx:subfield>
                <mx:subfield code="9">ess=nrl</mx:subfield>
              </mx:datafield>
        ''')

        table, notation, is_top_concept, parent_notation, caption = ClassificationRecord.parse_153(element)

        assert table is None
        assert is_top_concept is False
        assert notation == '332.0240081-332.0240088'
        assert parent_notation == '332.024001-332.024009'
        assert caption == 'Miscellaneous specific kinds of persons'


if __name__ == '__main__':
    unittest.main()
