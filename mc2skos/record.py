# encoding=utf8

import re
from datetime import datetime
import logging
from iso639 import languages

from .constants import Constants
from .element import Element

logger = logging.getLogger(__name__)


CONFIG = {
    'classification_schemes': {
        'ddc': {
            'uri': 'http://dewey.info/{collection}/{object}/e{edition}/'
        },
        'bkl': {
            'uri': 'http://uri.gbv.de/terminology/bk/{object}'
        },
        'utklklass': {
            'uri': lambda x: x['object'].replace('L ', 'http://data.ub.uio.no/lklass/L'),
            'scheme': 'http://data.ub.uio.no/lklass/',
        },
    },
    'subject_schemes': {
        'a': {
            'uri': 'http://id.loc.gov/authorities/subjects/{control_number}',
            'scheme': 'http://id.loc.gov/authorities/subjects',
        },
        'd': {
            'uri': 'http://lod.nal.usda.gov/nalt/{control_number}',
            'scheme': 'http://lod.nal.usda.gov/nalt/',
        },
        'usvd': {
            'uri': lambda x: x['control_number'].replace('USVD', 'http://data.ub.uio.no/usvd/c'),
            'scheme': 'http://data.ub.uio.no/usvd/',
        },
        'humord': {
            'uri': lambda x: x['control_number'].replace('HUME', 'http://data.ub.uio.no/humord/c'),
            'scheme': 'http://data.ub.uio.no/humord/',
        },
        'noubojur': {
            'uri': lambda x: 'http://data.ub.uio.no/lskjema/c%06d' % int(x['control_number'][4:]),
            'scheme': 'http://data.ub.uio.no/lskjema/',
        },
        'noubomn': {
            'uri': lambda x: x['control_number'].replace('REAL', 'http://data.ub.uio.no/realfagstermer/c'),
            'scheme': 'http://data.ub.uio.no/realfagstermer/',
        },
        'noubomr': {
            'uri': lambda x: x['control_number'].replace('SMR', 'http://data.ub.uio.no/mrtermer/c'),
            'scheme': 'http://data.ub.uio.no/mrtermer/',
        },
    },
}


class InvalidRecordError(RuntimeError):
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
        self.broader = []
        self.related = []
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
        self.classificationNumbers = []
        self.webDeweyExtras = {}
        self.deprecated = False
        self.is_top_concept = False
        self.notation = None
        self.scheme = None

        self.uri = None  # Concept URI
        self.scheme_uris = []  # Concept scheme URI

        self.uri_template = options.get('base_uri')
        self.scheme_uri_template = options.get('scheme_uri')

        self.parse(options or {})

    def get_uri(self, **kwargs):
        if self.uri_template is None:
            return None
        if callable(self.uri_template):
            return self.uri_template(kwargs)
        else:
            return self.uri_template.format(**kwargs)

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
        self.scheme_edition_numeric = None
        self.table_scheme_uri_template = options.get('table_scheme_uri')

        super(ClassificationRecord, self).__init__(record, options)

    def get_uri(self, **kwargs):
        kwargs['edition'] = self.scheme_edition_numeric
        return super(ClassificationRecord, self).get_uri(**kwargs)

    def generate_uris(self):
        # If URI templates have been provided as options, these takes precedence:
        if self.scheme_uri_template is not None:
            self.scheme_uris.append(self.scheme_uri_template.format(edition=self.scheme_edition_numeric))

        if self.record_type == Constants.TABLE_RECORD and self.table_scheme_uri_template is not None:
            self.scheme_uris.append(self.table_scheme_uri_template.format(edition=self.scheme_edition_numeric, table=self.table))

        # Generate URIs from scheme
        if self.scheme in CONFIG['classification_schemes']:
            if self.uri_template is None:
                cfg = CONFIG['classification_schemes'][self.scheme]
                self.uri_template = cfg['uri']
            if len(self.scheme_uris) == 0:
                if self.record_type == Constants.TABLE_RECORD:
                    table = self.table if self.table is not None else ''
                    self.scheme_uris.append(self.get_uri(collection='table', object=table))
                edition = 'edition' if self.scheme_edition is not None else ''
                self.scheme_uris.append(self.get_uri(collection='scheme', object=edition))

        # Record URI
        self.uri = self.get_uri(collection='class', object=self.notation)

    def parse(self, options):

        super(ClassificationRecord, self).parse(options)

        # 008
        value = self.record.text('mx:controlfield[@tag="008"]')
        self.created, self.record_type, self.number_type, self.display, self.synthesized, self.deprecated = self.parse_008(value)

        # 084: Classification Scheme and Edition
        self.scheme = self.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="a"]')
        self.scheme_edition = self.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="c"]')
        self.scheme_edition_numeric = re.sub('[^0-9]', '', self.scheme_edition or '')

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
            parent_uri = self.get_uri(collection='class', object=parent_notation)
            if parent_uri is not None:
                self.broader.append(parent_uri)

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
        # If URI templates have been provided as options, these takes precedence:
        if self.scheme_uri_template is not None:
            self.scheme_uris.append(self.scheme_uri_template)

        # Generate URIs from scheme
        if self.scheme in CONFIG['subject_schemes']:
            cfg = CONFIG['subject_schemes'][self.scheme]
            if self.uri_template is None and cfg.get('uri') is not None:
                self.uri_template = cfg['uri']
            if len(self.scheme_uris) == 0 and cfg.get('scheme') is not None:
                self.scheme_uris.append(cfg.get('scheme'))

        # Record URI
        self.uri = self.get_uri(control_number=self.control_number)

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
        if class_obj.get('scheme') in CONFIG['classification_schemes']:
            uri_tpl = CONFIG['classification_schemes'][class_obj['scheme']]['uri']
            if callable(uri_tpl):
                class_obj['uri'] = uri_tpl(class_obj)
            else:
                class_obj['uri'] = uri_tpl.format(**class_obj)

        return class_obj

    def parse(self, options):

        super(AuthorityRecord, self).parse(options)

        leader = self.record.text('mx:leader')
        if leader[5] in ['d', 'o', 's', 'x']:
            self.deprecated = True

        # 008
        field_008 = self.record.text('mx:controlfield[@tag="008"]')
        if field_008:
            self.created = datetime.strptime(field_008[:6], '%y%m%d')

        # Scheme / vocabulary code
        self.scheme = field_008[11]
        if self.scheme == 'z':
            self.scheme = self.record.text('mx:datafield[@tag="040"]/mx:subfield[@code="f"]')

        # Now we have enough information to generate URIs
        self.generate_uris()

        # 065: Other Classification Number
        el = self.record.first('mx:datafield[@tag="065"]')
        if el is not None:
            self.classificationNumbers.append(self.append_class_uri({
                'object': self.get_class_number(el),
                'scheme': el.text('mx:subfield[@code="2"]'),
            }))

        # 080: Universal Decimal Classification Number
        el = self.record.first('mx:datafield[@tag="080"]')
        if el is not None:
            self.classificationNumbers.append(self.append_class_uri({
                'object': self.get_class_number(el),
                'scheme': 'udc',
                'edition': el.text('mx:subfield[@code="2"]'),
            }))

        # 083: Dewey Decimal Classification Number
        el = self.record.first('mx:datafield[@tag="083"]')
        if el is not None:
            self.classificationNumbers.append(self.append_class_uri({
                'object': self.get_class_number(el),
                'scheme': 'ddc',
                'edition': el.text('mx:subfield[@code="2"]'),
            }))

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
                m = re.match('^\(.+\)(.+)$', local_id)
                if m:
                    local_id = m.group(1)
                if local_id.startswith('http'):
                    uri = local_id
                else:
                    uri = self.get_uri(control_number=local_id)
                if local_id:
                    if heading['node'].text('mx:subfield[@code="w"]') == 'g':
                        self.broader.append(uri)
                    else:
                        self.related.append(uri)

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
