# encoding=utf8

import re
from datetime import datetime
import logging
from iso639 import languages
from rdflib import URIRef
from rdflib.namespace import SKOS

from .constants import Constants
from .element import Element

logger = logging.getLogger(__name__)

CONFIG = {
    'classification_schemes': {
        'ddc': 'http://dewey.info/{collection}/{object}/e{edition}/',
        'bkl': 'http://uri.gbv.de/terminology/bk/{object}',
        'utklklass': {
            'concept': 'http://data.ub.uio.no/lklass/L{object[2:]}',
            'scheme': 'http://data.ub.uio.no/lklass/',
        },
    },
    'subject_schemes': {
        'a': {
            'concept': 'http://id.loc.gov/authorities/subjects/{control_number}',
            'scheme': 'http://id.loc.gov/authorities/subjects',
        },
        'd': 'http://lod.nal.usda.gov/nalt/{control_number}',
        'usvd': {
            'concept': 'http://data.ub.uio.no/usvd/c{control_number[4:]}',
            'scheme': 'http://data.ub.uio.no/usvd/',
        },
        'humord': {
            'concept': 'http://data.ub.uio.no/humord/c{control_number[4:]}',
            'scheme': 'http://data.ub.uio.no/humord/',
        },
        'noubojur': {
            'concept': 'http://data.ub.uio.no/lskjema/c{control_number[4:]:06d}',
            'scheme': 'http://data.ub.uio.no/lskjema/',
        },
        'noubomn': {
            'concept': 'http://data.ub.uio.no/realfagstermer/c{control_number[4:]}',
            'scheme': 'http://data.ub.uio.no/realfagstermer/',
        },
        'noubomr': {
            'concept': 'http://data.ub.uio.no/mrtermer/c{control_number[3:]}',
            'scheme': 'http://data.ub.uio.no/mrtermer/',
        },
    },
}


def is_uri(value):
    return value.startswith('http://') or value.startswith('https://')


def is_str(obj):
    try:
        return isinstance(obj, basestring)  # Python 2.x
    except NameError:
        return isinstance(obj, str)  # Python 3.x


class InvalidRecordError(RuntimeError):
    pass


class ConceptScheme(object):

    def __init__(self, code=None, concept_type=None, edition=None, options=None):
        self.code = code
        self.edition = edition
        self.edition_numeric = re.sub('[^0-9]', '', edition or '')
        self.config = {}

        if concept_type is not None:
            config = CONFIG[{
                AuthorityRecord: 'subject_schemes',
                ClassificationRecord: 'classification_schemes',
            }.get(concept_type)]
            if code in config:
                self.config = config[code]

        options = options or {}
        if options.get('base_uri'):
            self.config = {
                'concept': options.get('base_uri'),
                'scheme': options.get('scheme_uri'),
            }

    @staticmethod
    def from_record(record, options):

        if isinstance(record, AuthorityRecord):
            field_008 = record.record.text('mx:controlfield[@tag="008"]')
            if field_008:
                scheme_code = field_008[11]
                if scheme_code == 'z':
                    scheme_code = record.record.text('mx:datafield[@tag="040"]/mx:subfield[@code="f"]')

                if scheme_code:
                    return ConceptScheme(scheme_code, AuthorityRecord, options=options)

        if isinstance(record, ClassificationRecord):
            scheme_code = record.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="a"]')
            scheme_edition = record.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="c"]')
            if scheme_code:
                return ConceptScheme(scheme_code, ClassificationRecord, edition=scheme_edition, options=options)

        return UnknownConceptScheme(options=options)

    def get_uri(self, uri_type='concept', **kwargs):
        kwargs['edition'] = self.edition_numeric
        if uri_type == 'scheme':
            kwargs['control_number'] = ''

        if 'control_number' in kwargs:
            # Remove organization prefix in parenthesis:
            kwargs['control_number'] = re.sub('^\(.+\)(.+)$', '\\1', kwargs['control_number'])

        if self.config is None:
            return

        if is_str(self.config):
            uri_template = self.config
        else:
            if uri_type not in self.config:
                return None
            uri_template = self.config[uri_type]

        if not uri_template:
            return None

        # Process field[start:end]

        def process_formatter(matches):
            start = int(matches.group('start')) if matches.group('start') else None
            end = int(matches.group('end')) if matches.group('end') else None
            value = kwargs[matches.group('param')][start:end]
            formatter_str = '{0' + matches.group('formatter') + '}' if matches.group('formatter') else '{0}'
            if 'd' in formatter_str:
                value = int(value)
            elif 'f' in formatter_str:
                value = float(value)

            return formatter_str.format(value)

        uri_template = re.sub(
            '\{(?P<param>[a-z_]+)(?:\[(?P<start>\d+)?:(?P<end>\d+)?\])?(?P<formatter>[:!][^\}]+)?\}',
            process_formatter,
            uri_template
        )
        return uri_template.format(**kwargs)


class UnknownConceptScheme(ConceptScheme):
    pass


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
        self.scheme = ConceptScheme.from_record(self, options)

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
        for entry in self.record.all('mx:datafield[%s]' % ' or '.join(tags)):
            codes = ['@code="%s"' % code for code in ['a', 'x', 'y', 'z', 'v']]
            term_parts = entry.text('mx:subfield[%s]' % ' or '.join(codes), True)
            cn = entry.text('mx:subfield[@code="0"]')
            cni = None
            if cn is not None:
                cn = cn.split(')')
                if len(cn) == 2:
                    cn = cn[1]
                    cni = cn[0].lstrip('(')
                else:
                    cn = cn[0]
            yield {
                'value': '--'.join(term_parts),
                'node': entry,
                'control_number': cn,
                'control_number_identifier': cni,
            }

    def parse(self, options):

        # 001
        self.control_number = self.record.text('mx:controlfield[@tag="001"]')

        # 003
        self.control_number_identifier = self.record.text('mx:controlfield[@tag="003"]')

        # 005
        value = self.record.text('mx:controlfield[@tag="005"]')
        if value is not None:
            self.modified = datetime.strptime(value, '%Y%m%d%H%M%S.%f')

        # 040: Record Source
        lang = self.record.text('mx:datafield[@tag="040"]/mx:subfield[@code="b"]') or 'eng'
        self.lang = languages.get(part2b=lang).part1

    def is_public(self):
        return True


class ClassificationRecord(Record):

    def __init__(self, record, options=None):
        options = options or {}

        super(ClassificationRecord, self).__init__(record, options)

    def generate_uris(self):
        # Generate URIs from scheme
        self.scheme_uris = []

        if self.record_type == Constants.TABLE_RECORD:
            table = self.table if self.table is not None else ''
            uri = self.scheme.get_uri(uri_type='scheme', collection='table', object=table)
            if uri:
                self.scheme_uris.append(uri)

        obj = 'edition' if self.scheme.edition is not None else ''
        uri = self.scheme.get_uri(uri_type='scheme', collection='scheme', object=obj)
        if uri:
            self.scheme_uris.append(uri)

        # Record URI
        self.uri = self.scheme.get_uri(collection='class', object=self.notation)

    def parse(self, options):

        super(ClassificationRecord, self).parse(options)

        # 008
        value = self.record.text('mx:controlfield[@tag="008"]')
        self.created, self.record_type, self.number_type, self.display, self.synthesized, self.deprecated = self.parse_008(value)

        # 153: Classification number
        element = self.record.first('mx:datafield[@tag="153"]')
        if element is None:
            raise InvalidRecordError('Record does not have a 153 field')
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
            parent_uri = self.scheme.get_uri(collection='class', object=parent_notation)
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

        # 694 : ??? Note : Non-standard code for 684 'Auxiliary Instruction Note' ??
        # Example:
        #   <mx:datafield tag="694" ind2=" " ind1=" ">
        #     <mx:subfield code="i">De fleste verker om seletøy og tilbehør klassifiseres med hester i</mx:subfield>
        #     <mx:subfield code="a">636.10837</mx:subfield>
        #     <mx:subfield code="9">ess=nml</mx:subfield>
        #   </mx:datafield>
        #
        for entry in self.record.all('mx:datafield[@tag="694"]'):
            self.editorialNote.append(entry.stringify())

        # 7XX Index terms
        for heading in self.get_terms('7'):
            self.altLabel.append({
                'term': heading['value']
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
            logger.warning('Unknown value: %s', value[6])
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

        return created, record_type, number_type, display, synthesized, deprecated

    @staticmethod
    def parse_153(element):
        # Parse the 153 field

        table = None
        notation = None
        parent_notation = None
        buf = ''
        is_top_concept = True

        parts = []

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

    def is_public(self):
        if not self.display and not self.synthesized:
            # This is a record not displayed in standard schedules or tables,
            # and it is not a synthesized number (we want those).
            # It could be e.g. an "add table" number.
            logger.debug('Ignoring %s because: not intended for display', self.notation)
            return False

        if self.record_type not in [Constants.SCHEDULE_RECORD, Constants.TABLE_RECORD]:
            logger.debug('Ignoring %s because: type %s', self.notation, self.record_type)
            return False

        include_add_table_numbers = False  # @TODO: Make argparse option
        if self.notation.find(':') != -1 and not include_add_table_numbers:
            logger.debug('Ignoring %s because: add table number', self.notation)
            return False

        return True


class AuthorityRecord(Record):

    def __init__(self, record, options=None):
        super(AuthorityRecord, self).__init__(record, options)

    def generate_uris(self):
        # Generate URIs from scheme
        self.scheme_uris = []

        scheme_uri = self.scheme.get_uri(uri_type='scheme')
        if scheme_uri:
            self.scheme_uris.append(scheme_uri)

        # Record URI
        self.uri = self.scheme.get_uri(control_number=self.control_number)

    @staticmethod
    def get_class_number(el):
        number_start = el.text('mx:subfield[@code="a"]')
        number_end = el.text('mx:subfield[@code="b"]')
        if number_end is not None:
            return '{}-{}'.format(number_start, number_end)
        else:
            return number_start

    @staticmethod
    def append_class_uri(class_obj):
        scheme = ConceptScheme(class_obj.get('scheme'))
        class_obj['uri'] = scheme.get_uri(**class_obj)

        # if class_obj.get('scheme') in CONFIG['classification_schemes']:
        #     uri_tpl = CONFIG['classification_schemes'][class_obj['scheme']]['concept']
        #     if callable(uri_tpl):
        #         class_obj['uri'] = uri_tpl(class_obj)
        #     else:
        #         class_obj['uri'] = uri_tpl.format(**class_obj)

        return class_obj

    def append_relation(self, scheme, relation, **kwargs):
        uri = scheme.get_uri(**kwargs)
        if uri:
            self.relations.append({
                'uri': uri,
                'relation': relation,
            })

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
                ConceptScheme(el.text('mx:subfield[@code="2"]'), ClassificationRecord),
                SKOS.exactMatch,
                object=self.get_class_number(el)
            )

        # 080: Universal Decimal Classification Number
        el = self.record.first('mx:datafield[@tag="080"]')
        if el is not None:
            self.append_relation(
                ConceptScheme('udc', ClassificationRecord),
                SKOS.exactMatch,
                object=self.get_class_number(el)
            )

        # 083: Dewey Decimal Classification Number
        el = self.record.first('mx:datafield[@tag="083"]')
        if el is not None:
            self.append_relation(
                ConceptScheme('ddc', ClassificationRecord, edition=el.text('mx:subfield[@code="2"]')),
                SKOS.exactMatch,
                object=self.get_class_number(el)
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
                            self.scheme,
                            relation,
                            control_number=local_id
                        )

        # 667 : Nonpublic General Note
        # madsrdf:editorialNote
        for entry in self.record.all('mx:datafield[@tag="667"]'):
            self.editorialNote.append(entry.stringify())

        # 670 : Source Data Found
        # Citation for a consulted source in which information is found related in some
        # manner to the entity represented by the authority record or related entities.
        for entry in self.record.all('mx:datafield[@tag="670"]'):
            self.note.append('Source: ' + entry.stringify())

        # 677 : Definition
        for entry in self.record.all('mx:datafield[@tag="677"]'):
            self.definition.append(entry.stringify())

        # 678 : Biographical or Historical Data
        # Summary of the essential biographical, historical, or other information about the 1XX heading
        # madsrdf:note
        for entry in self.record.all('mx:datafield[@tag="678"]'):
            self.note.append(entry.stringify())

        # 680 : Public General Note
        # madsrdf:note
        for entry in self.record.all('mx:datafield[@tag="680"]'):
            self.note.append(entry.stringify())

        # 681 : Subject Example Tracing Note
        # madsrdf:exampleNote
        for entry in self.record.all('mx:datafield[@tag="681"]'):
            self.example.append(entry.stringify())

        # 682 : Deleted Heading Information
        # Explanation for the deletion of an established heading or subdivision record from an authority file.
        # madsrdf:changeNote
        for entry in self.record.all('mx:datafield[@tag="682"]'):
            self.changeNote.append(entry.stringify())

        # 688 : Application History Note
        # Information that documents changes in the application of a 1XX heading.
        # madsrdf:historyNote
        for entry in self.record.all('mx:datafield[@tag="688"]'):
            self.historyNote.append(entry.stringify())

        # 7XX: Heading Linking Entries
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

                        self.append_relation(
                            ConceptScheme(scheme_code, AuthorityRecord),
                            relation,
                            control_number=sf.text()
                        )
