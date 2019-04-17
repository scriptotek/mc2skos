# encoding=utf8

from datetime import datetime
import logging
from iso639 import languages
from rdflib import URIRef
from rdflib.namespace import SKOS

from .constants import Constants
from .element import Element
from .error import InvalidRecordError, UnknownSchemeError
from .util import is_uri

logger = logging.getLogger(__name__)


class DuplicateFilter(object):
    def __init__(self):
        self.msgs = set()

    def filter(self, record):
        rv = record.msg not in self.msgs
        self.msgs.add(record.msg)
        return rv


logger.addFilter(DuplicateFilter())


class Record(object):

    def __init__(self, record, options=None):
        options = options or {}
        if isinstance(record, Element):
            self.record = record
        else:
            self.record = Element(record)

        self.control_number = None
        self.control_number_identifier = None
        self.created = None
        self.modified = None
        self.lang = None
        self.prefLabel = None
        self.altLabel = []
        self.definition = []
        self.editorialNote = []
        self.note = []
        self.components = []
        self.scopeNote = []
        self.historyNote = []
        self.changeNote = []
        self.example = []
        self.relations = []
        self.webDeweyExtras = {}
        self.deprecated = False
        self.is_top_concept = False
        self.notation = None

        self.vocabularies = options['vocabularies']
        try:
            self.scheme = self.vocabularies.get_from_record(self)
        except UnknownSchemeError as e:
            e.control_number = self.record.text('mx:controlfield[@tag="001"]')
            raise

        self.uri = None  # Concept URI
        self.scheme_uris = []  # Concept scheme URI

        self.parse(options or {})

    def get_terms(self, base='1'):
        # X00 - Personal Name
        # X10 - Corporate Name
        # X11 - Meeting Name
        # X30 - Uniform Title
        # X47 - Named Event
        # X48 - Chronological
        # X50 - Topical
        # X51 - Geographic Name
        # X53 - Uncontrolled
        # X55 - Genre/Form Term
        # X62 - Medium of Performance Term
        tags = ['@tag="%s%s"' % (base, tag) for tag in ['00', '10', '11', '30', '47', '48', '50', '51', '53', '55', '62']]

        terms = []
        for entry in self.record.all('mx:datafield[%s]' % ' or '.join(tags)):

            def reducer(value, element):
                prefix = ' '
                suffix = ''

                if value == '':
                    prefix = ''
                elif element.get('code') == 'd' and value[-1] not in [',', ';']:
                    prefix = ' ('
                    suffix = ')'
                elif element.get('code') in ['x', 'y', 'z', 'v']:
                    prefix = '--'

                return value + prefix + element.text() + suffix

            label = entry.reduce(reducer, ['a', 'd', 'x', 'y', 'z', 'v'])

            # codes = ['@code="%s"' % code for code in ['a', 'd', 'x', 'y', 'z', 'v']]
            # term_parts = entry.text('mx:subfield[%s]' % ' or '.join(codes), True)
            cn = entry.text('mx:subfield[@code="0"]')
            cni = None
            if cn is not None:
                cn = cn.split(')')
                if len(cn) == 2:
                    cn = cn[1]
                    cni = cn[0].lstrip('(')
                else:
                    cn = cn[0]
            term = {
                'value': label,
                'node': entry,
                'control_number': cn,
                'control_number_identifier': cni,
            }
            if 'isCaption' in entry.get_ess_codes():
                terms.insert(0, term)
            else:
                terms.append(term)

        return terms

    def parse(self, options):

        # 001
        self.control_number = self.record.text('mx:controlfield[@tag="001"]')

        # 010 : If present, it takes precedence over 001.
        # <https://github.com/scriptotek/mc2skos/issues/42>
        value = self.record.text('mx:datafield[@tag="010"]/mx:subfield[@code="a"]')
        if value is not None:
            self.control_number = value

        # 016 : If present, it takes precedence over 001
        # <https://github.com/scriptotek/mc2skos/issues/42>
        value = self.record.text('mx:datafield[@tag="016"]/mx:subfield[@code="a"]')
        if value is not None:
            self.control_number = value

        # 003
        self.control_number_identifier = self.record.text('mx:controlfield[@tag="003"]')

        # 005
        value = self.record.text('mx:controlfield[@tag="005"]')
        if value is not None:
            try:
                self.modified = datetime.strptime(value, '%Y%m%d%H%M%S.%f')
            except ValueError:
                logger.warning('Record %s: Ignoring invalid date in 005 field: %s', self.control_number, value)

        # 040: Record Source
        lang = self.record.text('mx:datafield[@tag="040"]/mx:subfield[@code="b"]') or 'eng'
        self.lang = languages.get(part2b=lang).part1

    def is_public(self):
        return True

    def append_relation(self, scheme_code, scheme_type, relation, **kwargs):
        try:
            scheme = self.vocabularies.get(scheme_code, edition=kwargs.get('edition'))
            uri = scheme.uri('concept', **kwargs)
        except UnknownSchemeError:
            tag = ' in field %s' % kwargs.get('tag') if kwargs.get('tag') else ''
            logger.warning((
                'Found links to "%s"%s, but mc2skos doesn\'t know the URI pattern of'
                ' that vocabulary, so no SKOS mappings were generated. See'
                ' <https://github.com/scriptotek/mc2skos#uris> for more info.'
            ) % (scheme_code, tag))
            return

        if uri:
            self.relations.append({
                'uri': uri,
                'relation': relation,
            })

    def get_mappings(self):
        # Get a list of possible mappings.

        for field in self.record.all('mx:datafield[@tag="024"]'):
            control_number = field.text('mx:subfield[@code="a"]')
            scheme_code = field.text('mx:subfield[@code="2"]')
            if scheme_code != 'uri':
                yield {
                    'scheme_code': scheme_code,
                    'relation': SKOS.exactMatch,
                    'control_number': control_number,
                    'tag': '024',
                }

        for heading in self.get_terms('7'):
            relation = None
            for sf in heading['node'].all('mx:subfield'):
                if sf.get('code') == '4':
                    if is_uri(sf.text()):
                        relation = URIRef(sf.text())
                    else:
                        relation = {
                            '=EQ': SKOS.exactMatch,
                            '~EQ': SKOS.closeMatch,
                            'BM': SKOS.broadMatch,
                            'NM': SKOS.narrowMatch,
                            'RM': SKOS.relatedMatch,
                        }.get(sf.text())  # None if no match

                elif sf.get('code') == '0':
                    # Note: Default value might change in the future
                    relation = relation if relation else SKOS.closeMatch

                    if is_uri(sf.text()):
                        self.relations.append({
                            'uri': sf.text(),
                            'relation': relation,
                        })
                    else:
                        scheme_code = {
                            '0': 'a',  # Library of Congress Subject Headings
                            '1': 'b',  # LC subject headings for children's literature
                            '2': 'c',  # Medical Subject Headings
                            '3': 'd',  # National Agricultural Library subject authority file
                            '4': 'n',  # Source not specified
                            '5': 'k',  # Canadian Subject Headings
                            '6': 'v',  # Répertoire de vedettes-matière
                            '7': heading['node'].text('mx:subfield[@code="2"]'),  # Source specified in subfield $2
                        }.get(heading['node'].get('ind2'))

                        yield {
                            'scheme_code': scheme_code,
                            'relation': relation,
                            'control_number': sf.text(),
                            'tag': heading['node'].get('tag'),
                        }


class ClassificationRecord(Record):

    def __init__(self, record, options=None):
        options = options or {}

        super(ClassificationRecord, self).__init__(record, options)

    def generate_uris(self):
        # Generate URIs from scheme
        self.scheme_uris = []

        if self.record_type == Constants.TABLE_RECORD:
            table = self.table if self.table is not None else ''
            uri = self.scheme.uri('scheme', collection='table', object=table)
            if uri:
                self.scheme_uris.append(uri)

        obj = 'edition' if self.scheme.edition is not None else ''
        uri = self.scheme.uri('scheme', collection='scheme', object=obj)
        if uri:
            self.scheme_uris.append(uri)

        # Record URI
        self.uri = self.scheme.uri('concept', collection='class', object=self.notation, control_number=self.control_number)

    def parse(self, options):

        super(ClassificationRecord, self).parse(options)

        # 008
        value = self.record.text('mx:controlfield[@tag="008"]')
        self.created, self.record_type, self.number_type, self.display, self.synthesized, self.deprecated = self.parse_008(value)

        # 153: Classification number
        element = self.record.first('mx:datafield[@tag="153"]')
        if element is None:
            raise InvalidRecordError('153 field is missing', control_number=self.control_number)
        self.table, self.notation, self.is_top_concept, parent_notation, self.prefLabel = self.parse_153(element)

        if self.record_type is None:
            logger.warning('Record does not have a 008 field, will try to guess type.')
            if self.table is None:
                self.record_type = Constants.SCHEDULE_RECORD
            else:
                self.record_type = Constants.TABLE_RECORD

        # Now we have enough information to generate URIs
        self.generate_uris()
        if parent_notation is not None:
            parent_uri = self.scheme.uri('concept', collection='class', object=parent_notation)
            if parent_uri is not None:
                self.relations.append({
                    'uri': parent_uri,
                    'relation': SKOS.broader
                })

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
            self.editorialNote.append(entry.stringify())  # Constants.COMPLEX_SEE_REFERENCE

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
            self.editorialNote.append(entry.stringify())  # Constants.COMPLEX_SEE_ALSO_REFERENCE

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
                self.definition.append(entry.stringify())  # Constants.DEFINITION
            else:
                self.scopeNote.append(entry.stringify())  # Constants.SCOPE_NOTE
                topics = [t.capitalize() for t in entry.text('mx:subfield[@code="t"]', True)]
                for topic in topics:
                    if 'nvn' in ess:
                        self.webDeweyExtras['variantName'] = self.webDeweyExtras.get('variantName', []) + [topic]
                    elif 'nch' in ess:
                        self.webDeweyExtras['classHere'] = self.webDeweyExtras.get('classHere', []) + [topic]
                    elif 'nin' in ess:
                        self.webDeweyExtras['including'] = self.webDeweyExtras.get('including', []) + [topic]
                    elif 'nph' in ess:
                        self.webDeweyExtras['formerName'] = self.webDeweyExtras.get('formerName', []) + [topic]

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
            self.editorialNote.append(entry.stringify())  # Constants.APPLICATION_INSTRUCTION_NOTE

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
            self.historyNote.append(entry.stringify())  # Constants.HISTORY_NOTE

        # 684 : Auxiliary Instruction Note
        # 694 : ??? Note : Non-standard code for 684 'Auxiliary Instruction Note' ??
        # Example:
        #   <mx:datafield tag="694" ind2=" " ind1=" ">
        #     <mx:subfield code="i">De fleste verker om seletøy og tilbehør klassifiseres med hester i</mx:subfield>
        #     <mx:subfield code="a">636.10837</mx:subfield>
        #     <mx:subfield code="9">ess=nml</mx:subfield>
        #   </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="684" or @tag="694"]'):
            self.editorialNote.append(entry.stringify())

        # 7XX Index terms
        for heading in self.get_terms('7'):
            self.altLabel.append({
                'term': heading['value']
            })

        # 7XX: Heading Linking Entries
        for mapping in self.get_mappings():
            self.append_relation(
                mapping['scheme_code'],
                None,
                mapping['relation'],
                control_number=mapping['control_number'],
                tag=mapping['tag']
            )

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
                    if sf.text() is None:
                        logger.warning('Class %s has blank 765 $s subfield. This should be fixed.', self.notation)
                    else:
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
            return None, None, None, True, False, False

        created = datetime.strptime(value[:6], '%y%m%d')

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
            logger.warning('Unknown value in 008/6: %s', value[6])
            record_type = Constants.UNKNOWN

        if value[7] == 'a':
            number_type = Constants.SINGLE_NUMBER
        elif value[7] == 'b':
            number_type = Constants.NUMBER_SPAN
        elif value[7] == 'c':
            number_type = Constants.SUMMARY_NUMBER_SPAN
        else:
            number_type = Constants.UNKNOWN

        deprecated = False
        if value[8] == 'd' or value[8] == 'e':
            deprecated = True

        if value[12] == 'b':
            synthesized = True
        else:
            synthesized = False

        if value[13] == 'a':
            # Displayed in standard schedules or tables
            display = True
        elif value[13] == 'b':
            # Extended display
            # These records show up in search in the WebDewey interface
            display = True
        elif value[13] == 'h':
            # Historical information, not intended for display.
            # These records do not show up in search in the WebDewey interface
            display = False
        elif value[7] == 'n':
            # Other information, not intended for display
            # These records do not show up in search in the WebDewey interface
            display = False
        else:
            logger.warning('Unknown value in 008/13: %s', value[13])
            display = False

        return created, record_type, number_type, display, synthesized, deprecated

    @staticmethod
    def parse_153(element):
        # Parse the 153 field

        table = None
        add_table = None
        notation = None
        parent_notation = None
        buf = ''
        caption = None  # Note: Synthesized classes do not have captions, that's ok
        zbuf = ''
        is_top_concept = True
        parts = []

        buf = [{'code': sf.get('code'), 'value': sf.text()} for sf in element.all('mx:subfield')]

        mode = 'notation'
        for idx, subfield in enumerate(buf):
            if subfield['code'] == 'z':
                table = subfield['value']

            elif subfield['code'] == 'y':
                add_table = subfield['value']

            elif subfield['code'] == 'a' and mode == 'notation':
                if add_table == '1':
                    notation += ':'
                elif add_table is not None:
                    notation += ':%s;' % add_table
                elif table is not None:
                    notation = '%s--' % table
                else:
                    notation = ''
                notation += subfield['value']
                add_table = None

            elif subfield['code'] == 'c' and mode == 'notation':
                notation += '-' + subfield['value']

            elif subfield['code'] == 'e' and mode in ['notation', 'parent']:
                parent_notation = ''
                if add_table == '1':
                    parent_notation += ':'
                elif add_table is not None:
                    parent_notation += ';%s:' % add_table
                elif table is not None:
                    parent_notation = '%s--' % table
                parent_notation += subfield['value']
                add_table = None
                mode = 'parent'

            elif subfield['code'] == 'f' and mode == 'parent':
                parent_notation += '-' + subfield['value']

            elif subfield['code'] == 'j':
                caption = subfield['value']

            elif subfield['code'] == 'h':
                # In the ddc21 examples, the parent class numbers (153 $e, $f) are not included,
                # but the parent class headings are (153 $h). We do not make any attempt of mapping
                # the headings to the classes, but just take note that this is not a top concept.
                is_top_concept = False

            else:
                mode = 'other'

        if parent_notation is not None:
            is_top_concept = False

        return table, notation, is_top_concept, parent_notation, caption

    def is_public(self):
        if not self.display:
            # This is a record not displayed in standard schedules or tables
            # or in extended display. It could be a deleted (not deprecated)
            # class.
            logger.debug('%s is not intended for display', self.notation)
            return False

        if self.record_type not in [Constants.SCHEDULE_RECORD, Constants.TABLE_RECORD]:
            logger.debug('%s is a type %s', self.notation, self.record_type)
            return False

        include_add_table_numbers = False  # @TODO: Make argparse option
        if self.notation.find(':') != -1 and not include_add_table_numbers:
            logger.debug('%s is an add table number', self.notation)
            return False

        return True


class AuthorityRecord(Record):

    def __init__(self, record, options=None):
        super(AuthorityRecord, self).__init__(record, options)

    def generate_uris(self):
        # Generate URIs from scheme
        self.scheme_uris = []

        scheme_uri = self.scheme.uri('scheme')
        if scheme_uri:
            self.scheme_uris.append(scheme_uri)

        # Record URI
        self.uri = self.scheme.uri('concept', control_number=self.control_number)

    @staticmethod
    def get_class_number(el):
        number_start = el.text('mx:subfield[@code="a"]')
        number_end = el.text('mx:subfield[@code="b"]')
        if number_end is not None:
            return '{}-{}'.format(number_start, number_end)
        else:
            return number_start

    def parse(self, options):
        super(AuthorityRecord, self).parse(options)

        # Now we have enough information to generate URIs
        self.generate_uris()

        leader = self.record.text('mx:leader')
        if leader[5] in ['d', 'o', 's', 'x']:
            self.deprecated = True

        # 008
        field_008 = self.record.text('mx:controlfield[@tag="008"]')
        if field_008:
            self.created = datetime.strptime(field_008[:6], '%y%m%d')

        # 065: Other Classification Number
        el = self.record.first('mx:datafield[@tag="065"]')
        if el is not None:
            self.append_relation(
                el.text('mx:subfield[@code="2"]'),
                ClassificationRecord,
                SKOS.exactMatch,
                object=self.get_class_number(el),
                tag='065'
            )

        # 080: Universal Decimal Classification Number
        el = self.record.first('mx:datafield[@tag="080"]')
        if el is not None:
            self.append_relation(
                'udc',
                ClassificationRecord,
                SKOS.exactMatch,
                object=self.get_class_number(el),
                tag='080'
            )

        # 083: Dewey Decimal Classification Number
        el = self.record.first('mx:datafield[@tag="083"]')
        if el is not None:
            self.append_relation(
                'ddc',
                ClassificationRecord,
                SKOS.exactMatch,
                collection='class',
                object=self.get_class_number(el),
                edition=el.text('mx:subfield[@code="2"]'),
                tag='083'
            )

        # 1XX Heading
        for heading in self.get_terms('1'):
            self.prefLabel = heading['value']

        # 4XX: See From Tracings
        for heading in self.get_terms('4'):
            self.altLabel.append({
                'term': heading['value']
            })

        # 5XX: See Also From Tracings
        for heading in self.get_terms('5'):
            local_id = heading['node'].text('mx:subfield[@code="0"]')
            if local_id:
                if local_id:
                    sf_w = heading['node'].text('mx:subfield[@code="w"]')
                    sf_4 = heading['node'].text('mx:subfield[@code="4"]')

                    if sf_w == 'g':
                        relation = SKOS.broader
                    elif sf_w == 'h':
                        relation = SKOS.narrower
                    elif sf_w == 'r' and is_uri(sf_4):
                        relation = URIRef(sf_4)
                    else:
                        relation = SKOS.related

                    if is_uri(local_id):
                        self.relations.append({
                            'uri': uri,
                            'relation': relation,
                        })
                    else:
                        self.append_relation(
                            self.scheme.code,
                            self.scheme.type,
                            relation,
                            control_number=local_id,
                            tag=heading['node'].get('tag')
                        )

        # 667 : Nonpublic General Note
        # madsrdf:editorialNote
        for entry in self.record.all('mx:datafield[@tag="667"]'):
            self.editorialNote.append(entry.stringify(subfields=['a']))

        # 670 : Source Data Found
        # Citation for a consulted source in which information is found related in some
        # manner to the entity represented by the authority record or related entities.
        for entry in self.record.all('mx:datafield[@tag="670"]'):
            self.note.append('Source: ' + entry.stringify(subfields=['a']))

        # 677 : Definition
        for entry in self.record.all('mx:datafield[@tag="677"]'):
            self.definition.append(entry.stringify(subfields=['a']))

        # 678 : Biographical or Historical Data
        # Summary of the essential biographical, historical, or other information about the 1XX heading
        # madsrdf:note
        for entry in self.record.all('mx:datafield[@tag="678"]'):
            self.note.append(entry.stringify(subfields=['a', 'b']))

        # 680 : Public General Note
        # madsrdf:note
        for entry in self.record.all('mx:datafield[@tag="680"]'):
            self.note.append(entry.stringify(subfields=['a', 'i']))

        # 681 : Subject Example Tracing Note
        # madsrdf:exampleNote
        for entry in self.record.all('mx:datafield[@tag="681"]'):
            self.example.append(entry.stringify(subfields=['a', 'i']))

        # 682 : Deleted Heading Information
        # Explanation for the deletion of an established heading or subdivision record from an authority file.
        # madsrdf:changeNote
        for entry in self.record.all('mx:datafield[@tag="682"]'):
            self.changeNote.append(entry.stringify(subfields=['a', 'i']))

        # 688 : Application History Note
        # Information that documents changes in the application of a 1XX heading.
        # madsrdf:historyNote
        for entry in self.record.all('mx:datafield[@tag="688"]'):
            self.historyNote.append(entry.stringify(subfields=['a']))

        # 7XX: Heading Linking Entries
        for mapping in self.get_mappings():
            self.append_relation(
                mapping['scheme_code'],
                None,
                mapping['relation'],
                control_number=mapping['control_number'],
                tag=mapping['tag']
            )
