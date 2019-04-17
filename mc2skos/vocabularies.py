from future.utils import python_2_unicode_compatible
import re
import yaml
from .error import UnknownSchemeError
from .record import AuthorityRecord, ClassificationRecord
from .util import is_str


@python_2_unicode_compatible
class Vocabularies(object):

    def __init__(self):
        self.entries = {}
        self.default_scheme = None

    def __iter__(self):
        for val in self.entries.values():
            yield val

    def set_default_scheme(self, generic=None, concept=None, scheme=None, whitespace=None):
        # Set URI templates manually. This will override values in vocabulary.yml.
        if generic is None and concept is None and scheme is None:
            self.default_scheme = None
            return

        options = {
            'base_uri': generic,
            'concept': concept,
            'scheme': scheme,
            'whitespace': whitespace,
        }
        if scheme in self.entries:
            self.default_scheme = self.entries[scheme]
        else:
            self.default_scheme = ConceptScheme(options=options)

    def load_yaml(self, file):
        data = yaml.safe_load(file)
        for concept_type_key, vocabs in data.items():
            concept_type = {
                'classification_schemes': ClassificationRecord,
                'subject_schemes': AuthorityRecord,
            }.get(concept_type_key)
            for scheme_code, options in vocabs.items():
                if is_str(options):
                    options = {'base_uri': options}
                self.entries[scheme_code] = ConceptScheme(concept_type, scheme_code, options=options)

    def get(self, scheme_code, edition=None):
        if scheme_code == 'n':
            raise UnknownSchemeError()
        if scheme_code not in self.entries:
            raise UnknownSchemeError(scheme_code)
        scheme = self.entries[scheme_code]
        if edition is not None:
            key = '%s-%s' % (scheme_code, edition)
            if key not in self.entries:
                self.entries[key] = scheme.with_edition(edition)
            return self.entries[key]
        return scheme

    def get_from_record(self, record):

        if self.default_scheme is not None:
            return self.default_scheme

        if isinstance(record, AuthorityRecord):
            field_008 = record.record.text('mx:controlfield[@tag="008"]')
            if field_008:
                code = field_008[11]
                if code == 'z':
                    code = record.record.text('mx:datafield[@tag="040"]/mx:subfield[@code="f"]')

                if code:
                    return self.get(code)

        if isinstance(record, ClassificationRecord):
            code = record.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="a"]')
            edition = record.record.text('mx:datafield[@tag="084"]/mx:subfield[@code="c"]')
            if code:
                return self.get(code, edition=edition)

        raise UnknownSchemeError()


@python_2_unicode_compatible
class ConceptScheme(object):

    def __init__(self, concept_type=None, code=None, edition=None, options=None):
        options = options or {}
        self.type = concept_type
        self.code = code  # Can be None if URI template is specified in options
        self.edition = edition
        self.options = options
        self.edition_numeric = re.sub('[^0-9]', '', edition or '')

        self.uri_templates = {
            'concept': options.get('concept') or options.get('base_uri'),
            'scheme': options.get('scheme') or options.get('base_uri'),
        }

        self.whitespace = options.get('whitespace') or '-'

    def with_edition(self, edition):
        # Get a specific edition of this scheme
        return ConceptScheme(self.type, self.code, edition, self.options)

    def __repr__(self):
        if self.edition is not None:
            return u'%s (%s ed.)' % (self.code, self.edition)
        return u'%s' % (self.code)

    def uri(self, uri_type, **kwargs):
        if uri_type not in self.uri_templates:
            raise ValueError('Unknown URI type: %s' % uri_type)

        uri_template = self.uri_templates[uri_type]
        if uri_template is None:
            raise UnknownSchemeError(
                self.code,
                message='No URI template found for URIs of type "%s" in vocabulary "%s"' % (uri_type, self.code)
            )

        kwargs['edition'] = self.edition_numeric
        if uri_type == 'scheme':
            kwargs['control_number'] = ''

        if kwargs.get('control_number') is not None:
            # Remove organization prefix in parenthesis:
            kwargs['control_number'] = re.sub(r'^\(.+\)(.+)$', '\\1', kwargs['control_number'])

        # Process field[start:end]

        def process_formatter(matches):
            start = int(matches.group('start')) if matches.group('start') else None
            end = int(matches.group('end')) if matches.group('end') else None
            value = kwargs[matches.group('param')][start:end]
            if len(value) == 0:
                # Empty string can be used for the scheme URI.
                # Trying to convert this to decimal or float will fail!
                formatter_str = '{0}'
            else:
                formatter_str = '{0' + matches.group('formatter') + '}' if matches.group('formatter') else '{0}'
                if 'd' in formatter_str:
                    value = int(value)
                elif 'f' in formatter_str:
                    value = float(value)

            return formatter_str.format(value)

        uri_template = re.sub(
            r'\{(?P<param>[a-z_]+)(?:\[(?P<start>\d+)?:(?P<end>\d+)?\])?(?P<formatter>[:!][^\}]+)?\}',
            process_formatter,
            uri_template
        )

        uri = uri_template.format(**kwargs)

        # replace whitespaces in URI
        return uri.replace(' ', self.whitespace)
