#!/usr/bin/env python
# encoding=utf8
#
# Script to convert MARC 21 Classification records
# (serialized as MARCXML) to SKOS concepts. See
# README.md for for more information.

import sys
import re
import time
from datetime import datetime
from lxml import etree
from iso639 import languages
import argparse
from rdflib.namespace import OWL, RDF, SKOS, DCTERMS, XSD, Namespace
from rdflib import URIRef, Literal, Graph, BNode
from otsrdflib import OrderedTurtleSerializer
import json
import rdflib_jsonld.serializer as json_ld
import pkg_resources

import logging
import logging.handlers

from . import __version__
from .constants import Constants
from .element import Element
from .record import InvalidRecordError, ClassificationRecord, AuthorityRecord, CONFIG

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

WD = Namespace('http://data.ub.uio.no/webdewey-terms#')
MADS = Namespace('http://www.loc.gov/mads/rdf/v1#')


class UnknownSchemeError(RuntimeError):

    def __init__(self):
        super(UnknownSchemeError, self).__init__('Cannot generate URIs for unknown classification scheme or subject vocabulary.')


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

    # Add index terms as skos:altLabel
    if options.get('include_altlabels'):
        for label in record.altLabel:
            graph.add((record_uri, SKOS.altLabel, Literal(label['term'], lang=record.lang)))

    # Add relations (SKOS:broader, SKOS:narrower, SKOS:xxxMatch, etc.)
    for relation in record.relations:
        if relation.get('uri') is not None:
            graph.add((record_uri, relation.get('relation'), URIRef(relation['uri'])))

    # Add notes
    if options.get('include_notes'):
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
    for key, values in record.webDeweyExtras.items():
        for value in values:
            graph.add((record_uri, WD[key], Literal(value, lang=record.lang)))


def process_record(graph, rec, **kwargs):
    """Convert a single MARC21 classification or authority record to RDF."""
    rec = Element(rec)
    leader = rec.text('mx:leader')
    if leader is None:
        raise InvalidRecordError('Record does not have a leader')
    if leader[6] == 'w':
        rec = ClassificationRecord(rec, kwargs)
    elif leader[6] == 'z':
        rec = AuthorityRecord(rec, kwargs)
    else:
        raise InvalidRecordError('Record is not a Marc21 Classification or Authority record')

    if rec.uri is None:
        raise UnknownSchemeError()

    if rec.is_public():
        add_record_to_graph(graph, rec, kwargs)


def process_records(records, graph, options):
    n = 0
    for record in records:
        n += 1
        try:
            process_record(graph, record, **options)
        except InvalidRecordError as e:
            logger.warning('Ignoring record %d: %s', n, e)
            pass
        except UnknownSchemeError as e:
            logger.warning('Ignoring record %d: %s', n, e)
            pass

    return graph


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
    parser.add_argument('infile', nargs='?', help='Input XML file')
    parser.add_argument('outfile', nargs='?', help='Output RDF file')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='More verbose output')
    parser.add_argument('-o', '--outformat', dest='outformat', metavar='FORMAT', nargs='?',
                        help='Output format: turtle (default), jskos, or ndjson',
                        default='turtle')

    parser.add_argument('--include', dest='include', help='RDF file to loaded into the graph' +
                        '(e.g. to define a concept scheme). Must be the same format as {outformat}.')

    parser.add_argument('--uri', dest='base_uri', help='URI template')
    parser.add_argument('--scheme', dest='scheme_uri', help='SKOS scheme for all records, use {edition} to specify edition.')
#    parser.add_argument('--table_scheme', dest='table_scheme_uri', help='SKOS scheme for table records, use {edition} to specify edition.')

    parser.add_argument('--altlabels', '--indexterms', dest='altlabels', action='store_true',
                        help='Include altlabels (from 7XX or 4XX).')
    parser.add_argument('--notes', dest='notes', action='store_true',
                        help='Include note fields.')
    parser.add_argument('--components', dest='components', action='store_true',
                        help='Include component information from 765.')

    parser.add_argument('-l', '--list-schemes', dest='list_schemes', action='store_true',
                        help='List default concept schemes.')

    args = parser.parse_args()

    if args.list_schemes:
        print('Classification schemes:')
        for k, v in CONFIG['classification_schemes'].items():
            print(' - {}: <{}>'.format(k, v['uri']))
        print('Authority schemes:')
        for k, v in CONFIG['subject_schemes'].items():
            print(' - {}: <{}> / <{}>'.format(k, v.get('scheme'), v.get('uri')))
        return

    supported_formats = ['turtle', 'jskos', 'ndjson']
    if args.outformat not in supported_formats:
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

    in_file = args.infile

    options = {
        'base_uri': args.base_uri,
        'scheme_uri': args.scheme_uri,
        'include_altlabels': args.altlabels,
        'include_notes': args.notes,
        'include_components': args.components
    }

    process_records(get_records(in_file), graph, options)

    if not graph:
        logger.warn('RDF result is empty!')
        return

    if args.outfile and args.outfile != '-':
        out_file = open(args.outfile, 'wb')
    else:
        out_file = sys.stdout

    if args.outformat == 'turtle':
        # @TODO: Perhaps use OrderedTurtleSerializer if available, but fallback to default Turtle serializer if not?
        s = OrderedTurtleSerializer(graph)

        s.sorters = [
            ('/([0-9A-Z\-]+)\-\-([0-9.\-;:]+)/e', lambda x: 'T{}--{}'.format(x[0], x[1])),  # table numbers
            ('/([0-9.\-;:]+)/e', lambda x: 'A' + x[0]),  # standard schedule numbers
        ]

        s.serialize(out_file)

    elif args.outformat in ['jskos', 'ndjson']:
        s = pkg_resources.resource_stream(__name__, 'jskos-context.json')
        context = json.load(s)
        jskos = json_ld.from_rdf(graph, context)
        if args.outformat == 'jskos':
            jskos['@context'] = u'https://gbv.github.io/jskos/context.json'
            out_file.write(json.dumps(jskos, sort_keys=True, indent=2))
        else:
            for record in jskos['@graph'] if '@graph' in jskos else [jskos]:
                record['@context'] = u'https://gbv.github.io/jskos/context.json'
                out_file.write(json.dumps(record, sort_keys=True))
                out_file.write('\n')

    if out_file != sys.stdout:
        logger.info('Wrote %s: %s' % (args.outformat, args.outfile))
