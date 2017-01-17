#!/usr/bin/env python
# encoding=utf8
#
# Script to convert MARC 21 Classification records
# (serialized as MARCXML) to SKOS concepts. See
# README.md for for more information.

import sys
import re
import time
from lxml import etree
from iso639 import languages
import argparse
from rdflib.namespace import OWL, RDF, RDFS, SKOS, Namespace
from rdflib import URIRef, RDFS, Literal, Graph, BNode
from otsrdflib import OrderedTurtleSerializer

import logging
import logging.handlers

from . import __version__

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


WD = Namespace('http://data.ub.uio.no/webdewey-terms#')
MADS = Namespace('http://www.loc.gov/mads/rdf/v1#')

counts = {}

default_uri_templates = {
    "ddc": {
        "uri": "http://dewey.info/{collection}/{object}/e{edition}/"
    }
}


class Constants(object):
    SCHEDULE_RECORD = 'schedule_record'
    TABLE_RECORD = 'table_record'
    INTERNAL_SUMMARY_OF_SCHEDULE_NUMBER = 'internal_summary_of_schedule_number'
    EXTERNAL_SUMMARY = 'external_summary'
    INTERNAL_SUMMARY_OF_TABLE_NUMBER = 'internal_summary_of_table_number'
    MANUAL_NOTE_RECORD = 'manual_note_record'

    UNKNOWN = 'unknown'

    SINGLE_NUMBER = 'single_number'
    NUMBER_SPAN = 'number_span'
    SUMMARY_NUMBER_SPAN = 'summary_number_span'

    COMPLEX_SEE_REFERENCE = 'nce'
    COMPLEX_SEE_ALSO_REFERENCE = 'nsa'
    DEFINITION = 'ndf'
    SCOPE_NOTE = 'scope_note'
    APPLICATION_INSTRUCTION_NOTE = 'application_instruction_note'
    HISTORY_NOTE = 'history_note'
    AUXILIARY_INSTRUCTION_NOTE = 'auxiliary_instruction_note'


class InvalidRecordError(RuntimeError):
    pass


class Element(object):

    nsmap = {
        'mx': 'http://www.loc.gov/MARC21/slim',
        'marc': 'http://www.loc.gov/MARC21/slim',
    }

    def __init__(self, node):
        self.node = node

    def get(self, name):
        return self.node.get(name)

    def all(self, xpath):
        # Yields all nodes matching the xpath
        for res in self.node.xpath(xpath, namespaces=self.nsmap):
            yield Element(res)

    def first(self, xpath):
        # Returns first node or None
        for res in self.all(xpath):
            return res

    def text(self, xpath=None, all=False):
        # xpath: the xpath
        # all: True to return an array with the text content for all matching elements.
        #      False to return a string with the text content of the first matching element, or None.
        # Returns text content of first node or None
        if xpath is None:
            return self.node.text
        if all:
            return [res.node.text for res in self.all(xpath) if res.node.text is not None]
        for res in self.all(xpath):
            return res.node.text  # return text of first element

    def get_ess_codes(self):
        return [x[4:] for x in self.node.xpath('mx:subfield[@code="9"]/text()', namespaces=self.nsmap) if x.find('ess=') == 0]

    def stringify(self):
        note = ''
        for subfield in self.node.xpath('mx:subfield', namespaces=self.nsmap):
            c = subfield.get('code')
            if c in ['a', 'c', 'i', 't', 'x']:

                # Captions can include Processing Instruction tags, like in this example
                # (linebreaks added):
                #
                #   <mx:subfield xmlns:mx="http://www.loc.gov/MARC21/slim"
                #                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" code="t">
                #     <?ddc fotag="fo:inline" font-style="italic"?>L
                #       <?ddc fotag="fo:inline" vertical-align="super" font-size="70%"?>p
                #       <?ddc fotag="/fo:inline"?>
                #     <?ddc fotag="/fo:inline"?>-rom
                #   </mx:subfield>
                #
                # The code below just strips away the PI tags, giving "Lp-rom" for this example.

                children = subfield.getchildren()
                if len(children) != 0:
                    txt = ''
                    for child in children:
                        if child.tail is not None:
                            txt += child.tail
                else:
                    txt = subfield.text

                if txt is None:
                    continue

                if c == 'c':
                    note += '-'
                elif len(note) != 0 and not re.match(r'[.\?#@+,<>%~`!$^&\(\):;\]]', txt[0]):
                    note += ' '
                note += txt

        return note


class Record(object):

    def __init__(self, record, default_uri_templates=None, options=None):
        self.record = Element(record)

        self.base_uri = None
        self.scheme_uri = None
        self.table_scheme_uri = None
        self.default_uri_templates = default_uri_templates or {}
        self.notes = []
        self.indexterms = []
        self.components = []
        self.parse(options or {})

    def uri(self, collection, object):
        if self.base_uri is None:
            return None
        return URIRef(self.base_uri.format(collection=collection,
                                           object=object,
                                           edition=self.scheme_edition_numeric))

    def parse(self, options):

        # Leader
        self.leader = self.record.text('mx:leader')
        if self.leader is None:
            raise InvalidRecordError('Record does not have a leader')
        if self.leader[6] != 'w':  # w: classification, z: authority
            raise InvalidRecordError('Record is not a Marc21 Classification record')

        # 008
        value = self.record.text('mx:controlfield[@tag="008"]')
        self.record_type, self.number_type, self.display, self.synthesized = self.parse_008(value)

        # 040: Record Source
        lang = self.record.text('mx:datafield[@tag="040"]/mx:subfield[@code="b"]') or 'eng'
        self.lang = languages.get(part2b=lang).part1

        # 084: Classification Scheme and Edition
        self.scheme = self.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="a"]')
        self.scheme_edition = self.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="c"]')
        self.scheme_edition_numeric = re.sub('[^0-9]', '', self.scheme_edition or '')

        # 153: Classification number
        element = self.record.first('mx:datafield[@tag="153"]')
        if element is None:
            raise InvalidRecordError('Record does not have a 153 field')
        self.table, self.notation, self.is_top_concept, self.parent_notation, self.caption = self.parse_153(element)
        if self.record_type is None:
            logger.warn('Record does not have a 008 field, will try to guess type.')
            if self.table is None:
                self.record_type = Constants.SCHEDULE_RECORD
            else:
                self.record_type = Constants.TABLE_RECORD

        # Generate URI templates from scheme, if scheme is known
        if self.scheme in self.default_uri_templates:
            cfg = self.default_uri_templates[self.scheme]
            self.base_uri = cfg['uri']
            self.scheme_uri = self.uri('scheme', 'edition')
            self.table_scheme_uri = self.uri('table', self.table)

        # 253 : Complex See Reference (R)
        # Example:
        # <mx:datafield tag="253" ind1="2" ind2=" ">
        #   <mx:subfield code="i">Klassifiser</mx:subfield>
        #   <mx:subfield code="t">naturhistorie</mx:subfield>
        #   <mx:subfield code="i">i</mx:subfield>
        #   <mx:subfield code="a">508</mx:subfield>
        #   <mx:subfield code="9">ess=nce</mx:subfield>
        # </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="253"]'):
            self.notes.append({
                'type': Constants.COMPLEX_SEE_REFERENCE,
                'content': entry.stringify()
            })

        # 353 : Complex See Also Reference (R)
        # Example:
        # <mx:datafield tag="353" ind1=" " ind2=" ">
        #   <mx:subfield code="i">Se også</mx:subfield>
        #   <mx:subfield code="a">900</mx:subfield>
        #   <mx:subfield code="i">for en</mx:subfield>
        #   <mx:subfield code="t">bred beskrivelse av situasjon og vilkår for intellektuell virksomhet</mx:subfield>
        #   <mx:subfield code="9">ess=nsa</mx:subfield>
        # </mx:datafield>
        for entry in self.record.all('mx:datafield[@tag="353"]'):
            self.notes.append({
                'type': Constants.COMPLEX_SEE_ALSO_REFERENCE,
                'content': entry.stringify()
            })

        # 680 : Scope note
        # Example:
        # <mx:datafield tag="680" ind1="1" ind2=" ">
        #   <mx:subfield code="i">Her:</mx:subfield>
        #   <mx:subfield code="t">Addisjon</mx:subfield>
        #   <mx:subfield code="i">,</mx:subfield>
        #   <mx:subfield code="t">subtraksjon</mx:subfield>
        #   <mx:subfield code="i">,</mx:subfield>
        #   <mx:subfield code="t">multiplikasjon</mx:subfield>
        #   <mx:subfield code="i">,</mx:subfield>
        #   <mx:subfield code="t">divisjon</mx:subfield>
        #   <mx:subfield code="9">ess=nch</mx:subfield>
        # </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="680"]'):
            ess = entry.get_ess_codes()
            if 'ndf' in ess:
                note_type = Constants.DEFINITION
            else:
                note_type = Constants.SCOPE_NOTE
            self.notes.append({
                'type': note_type,
                'content': entry.stringify(),
                'ess': ess,
                'topics': [t.capitalize() for t in entry.text('mx:subfield[@code="t"]', True)]
            })

        # 683 : Application Instruction Note
        # Example:
        # <mx:datafield tag="683" ind1="1" ind2=" ">
        #   <mx:subfield code="i">Ordnes alfabetisk etter</mx:subfield>
        #   <mx:subfield code="t">navnet på datamaskinen eller prosessoren</mx:subfield>
        #   <mx:subfield code="i">, f.eks.</mx:subfield>
        #   <mx:subfield code="t">IBM System z9®</mx:subfield>
        #   <mx:subfield code="9">ess=nal</mx:subfield>
        # </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="683"]'):
            self.notes.append({
                'type': Constants.APPLICATION_INSTRUCTION_NOTE,
                'content': entry.stringify(),
                'ess': entry.get_ess_codes(),
            })

        # 685 : History note
        # Example:
        #  <mx:datafield tag="685" ind2="0" ind1="1">
        #    <mx:subfield code="i">Klassifiseres nå i</mx:subfield>
        #    <mx:subfield code="a">512.901</mx:subfield>
        #    <mx:subfield code="c">512.909</mx:subfield>
        #    <mx:subfield code="9">ess=nrl</mx:subfield>
        #  </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="685"]'):
            self.notes.append({
                'type': Constants.HISTORY_NOTE,
                'content': entry.stringify(),
                'ess': entry.get_ess_codes(),
            })

        # 694 : ??? Note : Wrong code for 684 'Auxiliary Instruction Note' ??
        # Example:
        #   <mx:datafield tag="694" ind2=" " ind1=" ">
        #     <mx:subfield code="i">De fleste verker om seletøy og tilbehør klassifiseres med hester i</mx:subfield>
        #     <mx:subfield code="a">636.10837</mx:subfield>
        #     <mx:subfield code="9">ess=nml</mx:subfield>
        #   </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="694"]'):
            self.notes.append({
                'type': Constants.AUXILIARY_INSTRUCTION_NOTE,
                'content': entry.stringify(),
                'ess': entry.get_ess_codes(),
            })

        # 700 - Index Term - Personal Name (R)
        # 710 - Index Term - Corporate Name (R)
        # 711 - Index Term - Meeting Name (R)
        # 730 - Index Term - Uniform Title (R)
        # 748 - Index Term - Chronological (R)
        # 750 - Index Term - Topical (R)
        # 751 - Index Term - Geographic Name (R)
        # 753 - Index Term - Uncontrolled (R)
        #
        tags = ['@tag="%s"' % tag for tag in ['700', '710', '711', '730', '748', '750', '751', '753']]
        for entry in self.record.all('mx:datafield[%s]' % ' or '.join(tags)):
            codes = ['@code="%s"' % code for code in ['a', 'x', 'y', 'z', 'v']]
            term_parts = entry.text('mx:subfield[%s]' % ' or '.join(codes), True)
            term = '--'.join(term_parts)
            if len(term) != 0:
                self.indexterms.append({
                    'term': term
                })

        # 765 : Synthesized Number Components
        for entry in reversed(list(self.record.all('mx:datafield[@tag="765"]'))):

            if entry.text('mx:subfield[@code="u"]') is None:
                logger.debug('Built number without components specified: %s', self.notation)

            table = ''
            rootno = ''
            for sf in entry.all('mx:subfield'):
                if sf.get('code') == 'b':    # Base number
                    if len(self.components) == 0:
                        self.components.append(table + sf.text())
                        table = ''
                elif sf.get('code') == 'r':    # Root number
                    rootno = sf.text()
                elif sf.get('code') == 'z':    # Table identification
                    table = '{0}--'.format(sf.text())
                # elif sf.get('code') == 't':    # Digits added from internal subarrangement or add table
                #     self.components.append(sf.text())
                elif sf.get('code') == 's':  # Digits added from classification number in schedule or external table
                    tmp = rootno + sf.text()
                    if len(tmp) > 3:
                        tmp = tmp[:3] + '.' + tmp[3:]
                    self.components.append(table + tmp)
                    table = ''
                # elif sf.get('code') not in ['9', 'u']:
                #     print sf.get('code'), sf.text, class_no

    @staticmethod
    def parse_008(value):
        # Parse the 008 field text

        if value is None:
            return None, None, True, False

        if value[6] == 'a':
            record_type = Constants.SCHEDULE_RECORD
        elif value[6] == 'b':
            record_type = Constants.TABLE_RECORD
        elif value[6] == 'e':
            record_type = Constants.EXTERNAL_SUMMARY
        elif value[6] == 'i':
            record_type = Constants.INTERNAL_SUMMARY_OF_SCHEDULE_NUMBER
        elif value[6] == 'j':
            record_type = Constants.INTERNAL_SUMMARY_OF_TABLE_NUMBER
        elif value[6] == 'm':
            record_type = Constants.MANUAL_NOTE_RECORD
        elif value[6] == '1':  # @TODO: Find out what this means! It's not documented
            record_type = Constants.SCHEDULE_RECORD
        else:
            logger.warn('Unknown value: %s', value[6])
            record_type = Constants.UNKNOWN

        if value[7] == 'a':
            number_type = Constants.SINGLE_NUMBER
        elif value[7] == 'b':
            number_type = Constants.NUMBER_SPAN
        elif value[7] == 'c':
            number_type = Constants.SUMMARY_NUMBER_SPAN
        else:
            number_type = Constants.UNKNOWN

        if value[12] == 'b':
            synthesized = True
        else:
            synthesized = False

        if value[13] == 'a':
            display = True
        elif value[13] == 'b':
            display = False
        elif value[13] == 'h':    # Historical information, not intended for display
            display = False
        elif value[7] == 'n':     # Other information, not intended for display
            display = False
        else:
            logger.debug(value[13])
            display = False

        return record_type, number_type, display, synthesized

    @staticmethod
    def parse_153(element):
        # Parse the 153 field

        table = None
        notation = None
        parent_notation = None
        buf = ''
        is_top_concept = True

        parts = [

        ]

        for sf in element.all('mx:subfield'):
            code = sf.get('code')
            val = sf.text()

            if code not in ['a', 'c', 'e', 'f', 'z', 'y']:
                # We expect everything else to be captions or notes, like in the example in
                # test_153::TestParse153::testComplexEntryWithUndocumentStuff
                break

            if code == 'z':
                if buf != '':
                    parts.append(buf)
                if len(parts) == 0:
                    table = val
                buf = val + '--'

            elif code == 'a':
                buf += val

            elif code == 'c':
                buf += '-' + val

            elif code == 'e':
                if len(parts) == 0:
                    # not a table number
                    parts.append(buf)
                    buf = ''
                buf += val
            elif code == 'f':
                buf += '-' + val

            elif code == 'y':
                # Add table number
                if val == '1':
                    buf += ':'
                else:
                    buf += ':{0};'.format(val)

        if buf != '':
            parts.append(buf)

        notation = parts[0]
        if len(parts) != 1:
            parent_notation = parts[1]
            is_top_concept = False

        if element.first('mx:subfield[@code="h"]') is not None:
            # In the ddc21 examples, the parent class numbers (153 $e, $f) are not included,
            # but the parent class headings are (153 $h). We do not make any attempt of mapping
            # the headings to the classes, but just take note that this is not a top concept.
            is_top_concept = False

        caption = element.text('mx:subfield[@code="j"]')
        # Note: Build number do not have caption, that's ok

        # if ess_code in ['si1', 'si2', 'ti1', 'ti2', 'i2', 'se1', 'se2', 'se3']:
        #     # Standard subdivision info? These records are not
        #     # part of the classification scheme tree.
        #     record_type = RecordTypes.UNKNOWN
        # elif notation.find(':') != -1:
        #     record_type = RecordTypes.ADD_TABLE_ENTRY
        # elif table is not None:
        #     record_type = RecordTypes.TABLE_ENTRY
        # else:
        #     record_type = RecordTypes.CLASS

        return table, notation, is_top_concept, parent_notation, caption

    def add_to_graph(self, graph, options):
        # Add record to graph

        uri = self.uri('class', self.notation)
        if uri is None:
            logger.debug('Ignoring %s because: No known concept scheme detected, and no manual URI template given', self.notation)
            return

        if not self.display and not self.synthesized:
            # This is a record not displayed in standard schedules or tables,
            # and it is not a synthesized number (we want those).
            # It could be e.g. an "add table" number.
            logger.debug('Ignoring %s because: not intended for display', self.notation)
            return

        if self.record_type not in [Constants.SCHEDULE_RECORD, Constants.TABLE_RECORD]:
            logger.debug('Ignoring %s because: type %s', self.notation, self.record_type)
            return

        include_add_table_numbers = False  # @TODO: Make argparse option
        if self.notation.find(':') != -1 and not include_add_table_numbers:
            logger.debug('Ignoring %s because: add table number', self.notation)
            return

        # logger.debug('Adding: %s', uri)

        # Strictly, we do not need to explicitly state here that <A> and <B> are instances
        # of skos:Concept, because such statements are entailed by the definition
        # of skos:semanticRelation.
        graph.add((uri, RDF.type, SKOS.Concept))

        # Add skos:topConceptOf or skos:inScheme
        if self.is_top_concept:
            if self.scheme_uri is not None:
                logger.info('Marking %s as topConcept', self.notation)
                graph.add((uri, SKOS.topConceptOf, self.scheme_uri))
            if self.record_type == Constants.TABLE_RECORD and self.table_scheme_uri is not None:
                graph.add((uri, SKOS.topConceptOf, self.table_scheme_uri))
        else:
            if self.scheme_uri is not None:
                graph.add((uri, SKOS.inScheme, self.scheme_uri))
            if self.record_type == Constants.TABLE_RECORD and self.table_scheme_uri is not None:
                graph.add((uri, SKOS.inScheme, self.table_scheme_uri))

        # Add skos:broader
        if self.parent_notation is not None:
            parent_uri = self.uri('class', self.parent_notation)
            graph.add((uri, SKOS.broader, parent_uri))

        # Add caption as skos:prefLabel
        if self.caption:
            graph.add((uri, SKOS.prefLabel, Literal(self.caption, lang=self.lang)))

        # Add classification number as skos:notation
        if self.notation:
            if self.record_type == Constants.TABLE_RECORD:  # OBS! Sjekk add tables
                graph.add((uri, SKOS.notation, Literal('T' + self.notation)))
            else:
                graph.add((uri, SKOS.notation, Literal(self.notation)))

        # Add index terms as skos:altLabel
        if options.get('include_indexterms'):
            for term in self.indexterms:
                graph.add((uri, SKOS.altLabel, Literal(term['term'], lang=self.lang)))

        # Add notes
        if options.get('include_notes'):
            for note in self.notes:
                # Complex see references
                if note['type'] in [Constants.COMPLEX_SEE_REFERENCE,
                                    Constants.COMPLEX_SEE_ALSO_REFERENCE,
                                    Constants.APPLICATION_INSTRUCTION_NOTE]:
                    graph.add((uri, SKOS.editorialNote, Literal(note['content'], lang=self.lang)))

                # Scope notes
                elif note['type'] == Constants.DEFINITION:
                    graph.add((uri, SKOS.definition, Literal(note['content'], lang=self.lang)))

                elif note['type'] == Constants.SCOPE_NOTE:
                    graph.add((uri, SKOS.scopeNote, Literal(note['content'], lang=self.lang)))

                    if 'nvn' in note['ess']:
                        for topic in note['topics']:
                            graph.add((uri, WD.variantName, Literal(topic, lang=self.lang)))
                    elif 'nch' in note['ess']:
                        for topic in note['topics']:
                            graph.add((uri, WD.classHere, Literal(topic, lang=self.lang)))
                    elif 'nin' in note['ess']:
                        for topic in note['topics']:
                            graph.add((uri, WD.including, Literal(topic, lang=self.lang)))
                    elif 'nph' in note['ess']:
                        for topic in note['topics']:
                            graph.add((uri, WD.formerName, Literal(topic, lang=self.lang)))

                # History notes
                elif note['type'] == Constants.HISTORY_NOTE:
                    graph.add((uri, SKOS.historyNote, Literal(note['content'], lang=self.lang)))

                if note['type'] == Constants.HISTORY_NOTE and 'ndn' in note['ess']:
                    graph.add((uri, OWL.deprecated, Literal(True)))

        # Add synthesized number components
        if options.get('include_components') and len(self.components) != 0:
            component = self.components.pop(0)
            component_uri = self.uri('class', component)
            b1 = BNode()
            graph.add((uri, MADS.componentList, b1))
            graph.add((b1, RDF.first, component_uri))

            for component in self.components:
                component_uri = self.uri('class', component)
                b2 = BNode()
                graph.add((b1, RDF.rest, b2))
                graph.add((b2, RDF.first, component_uri))
                b1 = b2

            graph.add((b1, RDF.rest, RDF.nil))


class UnknownClassificationScheme(RuntimeError):
    pass


def process_record(graph, rec, **kwargs):
    # Parse a single MARC21 classification record

    rec = Record(rec, default_uri_templates)

    base_uri = kwargs.get('base_uri')

    scheme_uri = kwargs.get('scheme_uri')
    if scheme_uri is not None:
        scheme_uri = URIRef(kwargs.get('scheme_uri').format(edition=rec.scheme_edition_numeric))

    table_scheme_uri = kwargs.get('table_scheme_uri')
    if table_scheme_uri is not None:
        table_scheme_uri = URIRef(kwargs.get('table_scheme_uri').format(edition=rec.scheme_edition_numeric, table=rec.table))

    if base_uri is not None and base_uri != '':
        rec.base_uri = base_uri
        rec.scheme_uri = scheme_uri
        rec.table_scheme_uri = table_scheme_uri

    rec.add_to_graph(graph, kwargs)


def get_records(in_file):
    logger.info('Parsing: %s', in_file)
    n = 0
    t0 = time.time()
    # recs = []
    for _, record in etree.iterparse(in_file, tag='{http://www.loc.gov/MARC21/slim}record'):
        yield record
        # recs.append(etree.tostring(record))
        record.clear()
        n += 1
        if n % 500 == 0:
            logger.info('Read %d records (%.f recs/sec)', n, (float(n) / (time.time() - t0)))
        # if len(recs) == 100:
        #     yield recs
        #     recs = []


def main():

    parser = argparse.ArgumentParser(description='Convert MARC21 Classification to SKOS/RDF')
    parser.add_argument('infile', nargs=1, help='Input XML file')
    parser.add_argument('outfile', nargs='?', help='Output RDF file')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='More verbose output')
    parser.add_argument('-o', '--outformat', dest='outformat', nargs='?',
                        help='Output serialization format. Default: turtle',
                        default='turtle')

    parser.add_argument('--uri', dest='base_uri', help='URI template')
    parser.add_argument('--scheme', dest='scheme_uri', help='SKOS scheme for all records.')
    parser.add_argument('--table_scheme', dest='table_scheme_uri', help='SKOS scheme for table records, use {edition} to specify edition.')

    parser.add_argument('--indexterms', dest='indexterms', action='store_true',
                        help='Include index terms from 7XX.')
    parser.add_argument('--notes', dest='notes', action='store_true',
                        help='Include note fields.')
    parser.add_argument('--components', dest='components', action='store_true',
                        help='Include component information from 765.')

    args = parser.parse_args()

    DCT = Namespace('http://purl.org/dc/terms/')

    graph = Graph()
    nm = graph.namespace_manager
    nm.bind('dct', DCT)
    nm.bind('skos', SKOS)
    nm.bind('wd', WD)
    nm.bind('mads', MADS)
    nm.bind('owl', OWL)

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    in_file = args.infile[0]
    if args.outformat != 'turtle':  # TODO: support more formats
        raise ValueError('output format not supported')

    options = {
        'base_uri': args.base_uri,
        'scheme_uri': args.scheme_uri,
        'table_scheme_uri': args.table_scheme_uri,
        'include_indexterms': args.indexterms,
        'include_notes': args.notes,
        'include_components': args.components
    }

    n = 0
    t0 = time.time()
    for record in get_records(in_file):
        try:
            res = process_record(graph, record, **options)
        except InvalidRecordError as e:
            # logger.debug('Ignoring invalid record: %s', e)
            pass  # ignore

    # @TODO: Perhaps use OrderedTurtleSerializer if available, but fallback to default Turtle serializer if not?
    s = OrderedTurtleSerializer(graph)

    s.sorters = [
        ('/([0-9A-Z\-]+)\-\-([0-9.\-;:]+)/e', lambda x: 'T{}--{}'.format(x[0], x[1])),  # table numbers
        ('/([0-9.\-;:]+)/e', lambda x: 'A' + x[0]),  # standard schedule numbers
    ]

    if args.outfile and args.outfile[0] != '-':
        s.serialize(open(out_file, 'wb'))
        logger.info('Wrote RDF: %s', out_file)
    else:
        s.serialize(sys.stdout)
