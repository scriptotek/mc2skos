#!/usr/bin/env python
# encoding=utf8
#
# Script to convert MARC 21 Classification records
# (serialized as MARCXML) to SKOS concepts. See
# README.md for more information.

import sys
import re
import time
import warnings
from datetime import datetime
from iso639 import languages
import argparse
from rdflib.namespace import OWL, RDF, SKOS, DCTERMS, XSD, Namespace
from rdflib import URIRef, Literal, Graph, BNode
from otsrdflib import OrderedTurtleSerializer
import json
import rdflib_jsonld.serializer as json_ld
import pkg_resources
import skosify

import logging
import logging.handlers

from . import __version__
from .constants import Constants
from .element import Element
from .record import InvalidRecordError, UnknownSchemeError, ClassificationRecord, AuthorityRecord, CONFIG, ConceptScheme
from .reader import MarcFileReader

logging.captureWarnings(True)
warnings.simplefilter('always', DeprecationWarning)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


WD = Namespace('http://data.ub.uio.no/webdewey-terms#')
MADS = Namespace('http://www.loc.gov/mads/rdf/v1#')


def add_record_to_graph(graph, record, options):
    # Add record to graph

    # logger.debug('Adding: %s', record.uri)

    # Strictly, we do not need to explicitly state here that <A> and <B> are instances
    # of skos:Concept, because such statements are entailed by the definition
    # of skos:semanticRelation.
    record_uri = URIRef(record.uri)

    graph.add((record_uri, RDF.type, SKOS.Concept))

    # Add skos:topConceptOf or skos:inScheme
    for scheme_uri in record.scheme_uris:
        if record.is_top_concept:
            graph.add((record_uri, SKOS.topConceptOf, URIRef(scheme_uri)))
        else:
            graph.add((record_uri, SKOS.inScheme, URIRef(scheme_uri)))

    if record.created is not None:
        graph.add((record_uri, DCTERMS.created, Literal(record.created.strftime('%F'), datatype=XSD.date)))

    if record.modified is not None:
        graph.add((record_uri, DCTERMS.modified, Literal(record.modified.strftime('%F'), datatype=XSD.date)))

    # Add classification number as skos:notation
    if record.notation:
        if record.record_type == Constants.TABLE_RECORD:  # OBS! Sjekk add tables
            graph.add((record_uri, SKOS.notation, Literal('T' + record.notation)))
        else:
            graph.add((record_uri, SKOS.notation, Literal(record.notation)))

    # Add local control number as dcterms:identifier
    if record.control_number:
        graph.add((record_uri, DCTERMS.identifier, Literal(record.control_number)))

    # Add caption as skos:prefLabel
    if record.prefLabel:
        graph.add((record_uri, SKOS.prefLabel, Literal(record.prefLabel, lang=record.lang)))
    elif options.get('include_webdewey') and len(record.altLabel) != 0:
        # If the --webdewey flag is set, we will use the first index term as prefLabel
        label = record.altLabel.pop(0)
        graph.add((record_uri, SKOS.prefLabel, Literal(label['term'], lang=record.lang)))

    # Add index terms as skos:altLabel
    if options.get('include_altlabels'):
        for label in record.altLabel:
            graph.add((record_uri, SKOS.altLabel, Literal(label['term'], lang=record.lang)))

    # Add relations (SKOS:broader, SKOS:narrower, SKOS:xxxMatch, etc.)
    for relation in record.relations:
        if relation.get('uri') is not None:
            graph.add((record_uri, relation.get('relation'), URIRef(relation['uri'])))

    # Add notes
    if not options.get('exclude_notes'):
        for note in record.definition:
            graph.add((record_uri, SKOS.definition, Literal(note, lang=record.lang)))

        for note in record.note:
            graph.add((record_uri, SKOS.note, Literal(note, lang=record.lang)))

        for note in record.editorialNote:
            graph.add((record_uri, SKOS.editorialNote, Literal(note, lang=record.lang)))

        for note in record.scopeNote:
            graph.add((record_uri, SKOS.scopeNote, Literal(note, lang=record.lang)))

        for note in record.historyNote:
            graph.add((record_uri, SKOS.historyNote, Literal(note, lang=record.lang)))

        for note in record.changeNote:
            graph.add((record_uri, SKOS.changeNote, Literal(note, lang=record.lang)))

        for note in record.example:
            graph.add((record_uri, SKOS.example, Literal(note, lang=record.lang)))

    # Deprecated?
    if record.deprecated:
        graph.add((record_uri, OWL.deprecated, Literal(True)))

    # Add synthesized number components
    if options.get('include_components') and len(record.components) != 0:
        component = record.components.pop(0)
        component_uri = URIRef(record.scheme.get_uri(collection='class', object=component))
        b1 = BNode()
        graph.add((record_uri, MADS.componentList, b1))
        graph.add((b1, RDF.first, component_uri))

        for component in record.components:
            component_uri = URIRef(record.scheme.get_uri(collection='class', object=component))
            b2 = BNode()
            graph.add((b1, RDF.rest, b2))
            graph.add((b2, RDF.first, component_uri))
            b1 = b2

        graph.add((b1, RDF.rest, RDF.nil))

    # Add webDewey extras
    if options.get('include_webdewey'):
        for key, values in record.webDeweyExtras.items():
            for value in values:
                graph.add((record_uri, WD[key], Literal(value, lang=record.lang)))


def process_record(graph, rec, **kwargs):
    """Convert a single MARC21 classification or authority record to RDF."""
    el = Element(rec)
    leader = el.text('mx:leader')
    if leader is None:
        raise InvalidRecordError('Record does not have a leader',
                                 control_number=el.text('mx:controlfield[@tag="001"]'))
    if leader[6] == 'w':
        if kwargs.get('skip_classification'):
            return
        rec = ClassificationRecord(el, kwargs)
    elif leader[6] == 'z':
        if kwargs.get('skip_authority'):
            return
        rec = AuthorityRecord(el, kwargs)
    else:
        raise InvalidRecordError('Record is not a Marc21 Classification or Authority record',
                                 control_number=el.text('mx:controlfield[@tag="001"]'))

    if rec.is_public():
        add_record_to_graph(graph, rec, kwargs)


def process_records(records, graph=None, **options):
    n = 0
    if graph is None:
        graph = Graph()
    for record in records:
        n += 1
        try:
            process_record(graph, record, **options)
        except InvalidRecordError as e:
            record_id = e.control_number or '#%d' % n
            logger.warning('Ignoring record %s: %s', record_id, e)

    if options.get('expand'):
        logger.info('Expanding RDF via basic SKOS inference')
        skosify.infer.skos_related(graph)
        skosify.infer.skos_topConcept(graph)
        skosify.infer.skos_hierarchical(graph, narrower=True)

    if options.get('skosify'):
        logger.info('Running Skosify with config file %s', options['skosify'])
        config = skosify.config(options['skosify'])
        graph = skosify.skosify(graph, **config)

    return graph


def main():

    parser = argparse.ArgumentParser(description='Convert MARC21 Classification to SKOS/RDF')
    parser.add_argument('infile', nargs='?', help='Input XML file')
    parser.add_argument('outfile', nargs='?', help='Output RDF file')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='More verbose output')
    parser.add_argument('-o', '--outformat', dest='outformat', metavar='FORMAT', nargs='?',
                        help='Output format: turtle (default), jskos, or ndjson')

    parser.add_argument('--include', dest='include', help='RDF file to loaded into the graph' +
                        '(e.g. to define a concept scheme). Must be the same format as {outformat}.')

    parser.add_argument('--uri', dest='base_uri', help='URI template')
    parser.add_argument('--scheme', dest='scheme_uri', help='SKOS scheme for all records, use {edition} to specify edition.')
#    parser.add_argument('--table_scheme', dest='table_scheme_uri', help='SKOS scheme for table records, use {edition} to specify edition.')

    parser.add_argument('--altlabels', '--indexterms', dest='altlabels', action='store_true',
                        help='Include altlabels (from 7XX or 4XX).')
    parser.add_argument('--notes', dest='notes', action='store_true',
                        help='Include note fields (DEPRECATED as including notes is now the default).')
    parser.add_argument('--exclude_notes', dest='exclude_notes', action='store_true',
                        help='Exclude note fields.')
    parser.add_argument('--components', dest='components', action='store_true',
                        help='Include component information from 765.')
    parser.add_argument('--webdewey', dest='webdewey', action='store_true',
                        help='Include non-standard WebDewey notes from 680.')
    parser.add_argument('--skip-classification', dest='skip_classification', action='store_true',
                        help='Skip classification records')
    parser.add_argument('--skip-authority', dest='skip_authority', action='store_true',
                        help='Skip authority records')
    parser.add_argument('--expand', dest='expand', action='store_true',
                        help='Use Skosify to infer skos:hasTopConcept, skos:narrower and skos:related')
    parser.add_argument('--skosify', dest='skosify',
                        help='Run Skosify with given configuration file')

    parser.add_argument('-l', '--list-schemes', dest='list_schemes', action='store_true',
                        help='List default concept schemes.')

    args = parser.parse_args()

    if args.notes:
        warnings.warn('--notes is deprecated as including notes is now the default. '
                      'The inverse option --exclude_notes has been added to exclude notes.',
                      DeprecationWarning)

    if args.list_schemes:
        print('Classification schemes:')
        for k in CONFIG['classification_schemes'].keys():
            scheme = ConceptScheme(k, ClassificationRecord)
            print('- %s' % scheme)
        print('Authority vocabularies:')
        for k in CONFIG['subject_schemes'].keys():
            scheme = ConceptScheme(k, AuthorityRecord)
            print('- %s' % scheme)
        return

    supported_formats = ['turtle', 'jskos', 'ndjson']
    if not args.outformat and args.outfile:
        ext = args.outfile.rpartition('.')[-1]
        if ext in supported_formats:
            args.outformat = ext
    if not args.outformat:
        args.outformat = 'turtle'
    elif args.outformat not in supported_formats:
        raise ValueError("Format not supported, must be one of '%s'." % "', '".join(supported_formats))

    graph = Graph()
    if args.include:
        if args.outformat == 'turtle':
            graph.load(args.include, format='turtle')
        else:
            graph.load(args.include, format='json-ld')

    nm = graph.namespace_manager
    nm.bind('dcterms', DCTERMS)
    nm.bind('skos', SKOS)
    nm.bind('wd', WD)
    nm.bind('mads', MADS)
    nm.bind('owl', OWL)

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    if args.infile is None:
        raise ValueError('Filename not specified')

    options = {
        'base_uri': args.base_uri,
        'scheme_uri': args.scheme_uri,
        'include_altlabels': args.altlabels,
        'exclude_notes': args.exclude_notes,
        'include_components': args.components,
        'include_webdewey': args.webdewey,
        'skip_classification': args.skip_classification,
        'skip_authority': args.skip_authority,
        'expand': args.expand,
        'skosify': args.skosify,
    }

    marc = MarcFileReader(args.infile)
    graph = process_records(marc.records(), graph, **options)

    if not graph:
        logger.warning('RDF result is empty!')
        return

    if args.outfile and args.outfile != '-':
        out_file = open(args.outfile, 'wb')
    else:
        if (sys.version_info > (3, 0)):
            out_file = sys.stdout.buffer
        else:
            out_file = sys.stdout

    if args.outformat == 'turtle':
        # @TODO: Perhaps use OrderedTurtleSerializer if available, but fallback to default Turtle serializer if not?
        serializer = OrderedTurtleSerializer(graph)

        serializer.class_order = [
            SKOS.ConceptScheme,
            SKOS.Concept,
        ]
        serializer.sorters = [
            (r'/([0-9A-Z\-]+)--([0-9.\-;:]+)/e', lambda x: 'C{}--{}'.format(x[0], x[1])),  # table numbers
            (r'/([0-9.\-;:]+)/e', lambda x: 'B' + x[0]),  # standard schedule numbers
            (r'^(.+)$', lambda x: 'A' + x[0]),  # fallback
        ]

        serializer.serialize(out_file)

    elif args.outformat in ['jskos', 'ndjson']:
        s = pkg_resources.resource_string(__name__, 'jskos-context.json').decode('utf-8')
        context = json.loads(s)
        jskos = json_ld.from_rdf(graph, context)
        if args.outformat == 'jskos':
            jskos['@context'] = u'https://gbv.github.io/jskos/context.json'
            out_file.write(json.dumps(jskos, sort_keys=True, indent=2).encode('utf-8'))
        else:
            for record in jskos['@graph'] if '@graph' in jskos else [jskos]:
                record['@context'] = u'https://gbv.github.io/jskos/context.json'
                out_file.write(json.dumps(record, sort_keys=True).encode('utf-8') + b'\n')

    if out_file != sys.stdout:
        logger.info('Wrote %s: %s' % (args.outformat, args.outfile))
