#!/usr/bin/env python
# encoding=utf8
#
# Script to convert MARC 21 Classification records
# (serialized as MARCXML) to SKOS concepts. See
# README.md for for more information.
#
# Usage:
#
#   $ python mc2skos.py infile.xml outfile.rdf
#

import sys
import re
from lxml import etree
import argparse
from rdflib.namespace import OWL, RDF, RDFS, SKOS, Namespace
from rdflib import URIRef, RDFS, Literal, Graph

import logging
import logging.handlers

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


g = Graph()
WD = Namespace('http://data.ub.uio.no/webdewey-terms#')
dct = Namespace('http://purl.org/dc/terms/')
nm = g.namespace_manager
nm.bind('dct', dct)
nm.bind('skos', SKOS)
nm.bind('wd', WD)
nm.bind('owl', OWL)

classification_schemes = {
    'ddc': {
        '23no': {'ns': Namespace('http://dewey.info/class/'), 'el': '{class_no}/e23/'}
    }
}

counts = {}


def stringify(nodes):
    note = ''
    for subfield in nodes:
        c = subfield.get('code')
        if c in ['a', 'c', 'i', 't', 'x']:
            children = subfield.getchildren()

            # because this can happen...
            # <mx:subfield xmlns:mx="http://www.loc.gov/MARC21/slim" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" code="t"><?ddc fotag="fo:inline" font-style="italic"?>L<?ddc fotag="fo:inline" vertical-align="super" font-size="70%"?>p<?ddc fotag="/fo:inline"?><?ddc fotag="/fo:inline"?>-rom</mx:subfield>

            if len(children) != 0:
                txt = ''
                for child in children:
                    if child.tail is not None:
                        txt += child.tail
            else:
                txt = subfield.text

            if c == 'c':
                note += '-'
            elif len(note) != 0 and not re.match(r'[.\?#@+,<>%~`!$^&\(\):;\]]', txt[0]):
                note += ' '
            note += txt

    return note


def get_ess(node, nsmap):
    # Get the first WebDewey 'ess' property
    return [x.replace('ess=', '') for x in node.xpath('mx:subfield[@code="9"]/text()[1]', namespaces=nsmap)]


def process_record(rec, parent_table, nsmap):
    # Parse a single MARC21 classification record
    class_no = ''

    leader = rec.xpath('mx:leader', namespaces=nsmap)[0].text
    if leader[6] != 'w':  # w: classification, z: authority
        return

    out = {'notes': [], 'scope_notes': [], 'history_notes': [], 'index_terms': [], 'parents': []}

    # Parse 084: Classification Scheme and Edition
    r = rec.xpath('mx:datafield[@tag="084"]', namespaces=nsmap)
    if not r:
        return 'records missing 084 field'

    f084 = r[0]
    scheme = [x for x in f084.xpath('mx:subfield[@code="a"]/text()', namespaces=nsmap)]
    edt = [x for x in f084.xpath('mx:subfield[@code="c"]/text()', namespaces=nsmap)]
    if len(scheme) != 1 or len(edt) != 1:
        logger.debug('Ignoring record missing scheme or edition')
        return 'records missing classification scheme or edition'
    out['scheme'] = scheme[0]
    out['edition'] = edt[0]

    # Parse 153: Classification number
    r = rec.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)
    if not r:
        return 'records missing 153 field'
    f153 = r[0]

    # $a - Classification number--single number or beginning number of span (R)
    class_no = [x for x in f153.xpath('mx:subfield[@code="a"]/text()', namespaces=nsmap)]

    # $c - Classification number--ending number of span (R)
    endnumber = [x for x in f153.xpath('mx:subfield[@code="c"]/text()[1]', namespaces=nsmap)]
    if len(endnumber) != 0:
        # This record representes a span. We skip such records
        logger.debug('Ignoring number span record: %s-%s', class_no[0], endnumber[0])
        return 'number span records'

    if len(class_no) > 2:
        logger.debug('Ignoring record with > 2 parts: %s', class_no)
        return 'records with more than one subdivision'
    class_no = ':'.join(class_no)
    out['class_no'] = class_no

    ess = [x for x in f153.xpath('mx:subfield[@code="9"]/text()', namespaces=nsmap)]
    if 'ess=si1' in ess:
        # Standard subdivision info? These records miss 153 $e as well and are not
        # part of the classification scheme tree.
        logger.debug('Ignoring record having $9 ess=si1: %s', class_no)
        return 'records having $9 ess=si1'
    elif 'ess=si2' in ess:
        # Standard subdivision info? These records miss 153 $j as well and are not
        # part of the classification scheme tree.
        logger.debug('Ignoring record having $9 ess=si2: %s', class_no)
        return 'records having $9 ess=si2'

    # $j - Caption (NR)
    try:
        out['caption'] = f153.xpath('mx:subfield[@code="j"]/text()[1]', namespaces=nsmap)[0]
    except IndexError:
        pass  # Build number without caption, that's ok
        # print etree.tounicode(f153, pretty_print=True)
        # return 'missing 153 $j'

    # $e - Classification number hierarchy--single number or beginning number of span (R)
    if out['class_no'] in parent_table:
        p = parent_table[out['class_no']]
        while p.find('-') != -1:
            # print 'parent of ', out['parent'], ' is ', parent_table[out['parent']]
            p = parent_table[p]
        out['parents'].append(p)
    else:
        logger.error('Records missing parent: %s', out['class_no'])

    # Generate URI
    try:
        scheme = classification_schemes[out['scheme']][out['edition']]
    except:
        logger.error('Unknown class scheme or edition!')
        raise

    # Appended / is necessary for dewey.info URLs to be dereferable
    uri = scheme['ns'][scheme['el'].format(class_no=out['class_no'])]

    existing = [x for x in g.triples((uri, None, None))]
    if len(existing) != 0:
        logger.warning('Duplicate records for %s', out['class_no'])
        return 'duplicate records'
        # sys.exit(1)

    # Strictly, we do not need to explicitly state here that <A> and <B> are instances
    # of skos:Concept, because such statements are entailed by the definition
    # of skos:semanticRelation.
    g.add((uri, RDF.type, SKOS.Concept))

    # Add caption as skos:prefLabel
    if 'caption' in out:
        g.add((uri, SKOS.prefLabel, Literal(out['caption'], lang='nb')))

    # Add classification number as skos:notation
    if 'class_no' in out:
        g.add((uri, SKOS.notation, Literal(out['class_no'])))

    # Add hierarchy as skos:broader
    for parent in out['parents']:
        if parent != out['class_no']:
            g.add((uri, SKOS.broader, scheme['ns'][scheme['el'].format(class_no=parent)]))

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
    for entry in rec.xpath('mx:datafield[@tag="253"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        g.add((uri, SKOS.editorialNote, Literal(note, lang='nb')))

    # 353 : Complex See Also Reference (R)
    # Example:
    # <mx:datafield tag="353" ind1=" " ind2=" ">
    #   <mx:subfield code="i">Se også</mx:subfield>
    #   <mx:subfield code="a">900</mx:subfield>
    #   <mx:subfield code="i">for en</mx:subfield>
    #   <mx:subfield code="t">bred beskrivelse av situasjon og vilkår for intellektuell virksomhet</mx:subfield>
    #   <mx:subfield code="9">ess=nsa</mx:subfield>
    # </mx:datafield>
    for entry in rec.xpath('mx:datafield[@tag="353"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        g.add((uri, SKOS.editorialNote, Literal(note, lang='nb')))

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
    for entry in rec.xpath('mx:datafield[@tag="680"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        g.add((uri, SKOS.scopeNote, Literal(note, lang='nb')))
        ess = get_ess(entry, nsmap)
        if 'ndf' in ess:
            g.add((uri, SKOS.definition, Literal(note, lang='nb')))
        elif 'nvn' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.variantName, Literal(t, lang='nb')))
        elif 'nch' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.classHere, Literal(t, lang='nb')))
        elif 'nin' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.including, Literal(t, lang='nb')))
        elif 'nph' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.formerName, Literal(t, lang='nb')))

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
    for entry in rec.xpath('mx:datafield[@tag="683"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        g.add((uri, SKOS.editorialNote, Literal(note, lang='nb')))

    # 685 : History note
    # Example:
    #  <mx:datafield tag="685" ind2="0" ind1="1">
    #    <mx:subfield code="i">Klassifiseres nå i</mx:subfield>
    #    <mx:subfield code="a">512.901</mx:subfield>
    #    <mx:subfield code="c">512.909</mx:subfield>
    #    <mx:subfield code="9">ess=nrl</mx:subfield>
    #  </mx:datafield>
    #
    for entry in rec.xpath('mx:datafield[@tag="685"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        g.add((uri, SKOS.historyNote, Literal(note, lang='nb')))
        ess = get_ess(entry, nsmap)
        if 'ndn' in ess:
            g.add((uri, OWL.deprecated, Literal(True)))

    # 750 : Index term
    # String order: $a : $x : $v : $y : $z
    for entry in rec.xpath('mx:datafield[@tag="750"]', namespaces=nsmap):
        term = []
        for x in ['a', 'x', 'y', 'z']:
            term.extend(entry.xpath('mx:subfield[@code="%s"]/text()' % (x), namespaces=nsmap))
        term = ' : '.join(term)

        if term == '':
            return 'records having empty index terms'
        if 'caption' not in out or term != out['caption']:
            g.add((uri, SKOS.altLabel, Literal(term, lang='nb')))

    return 'valid records'


def get_parent(node, nsmap):

    node = node.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)

    if len(node) != 1:
        return

    node = node[0]

    class_no1 = node.xpath('mx:subfield[@code="a"]/text()', namespaces=nsmap)
    class_no1 = ':'.join(class_no1)

    class_no2 = node.xpath('mx:subfield[@code="c"]/text()[1]', namespaces=nsmap)
    if len(class_no2) == 0:
        class_no = class_no1
    else:
        class_no = '%s-%s' % (class_no1, class_no2[0])

    par1 = node.xpath('mx:subfield[@code="e"]/text()[1]', namespaces=nsmap)
    if len(par1) == 0:
        return
    par1 = par1[0]

    par2 = node.xpath('mx:subfield[@code="f"]/text()[1]', namespaces=nsmap)
    if len(par2) == 0:
        return [class_no, par1]

    par2 = par2[0]
    return [class_no, '%s-%s' % (par1, par2)]

    # node = doc.xpath('//mx:datafield[@tag="153"][count(./mx:subfield[@code="a"]) = 1 and ./mx:subfield[@code="a"] = "%s" and ./mx:subfield[@code="c"] = "%s"]' % (par1, par2),
    #                  namespaces={'mx': 'http://www.loc.gov/MARC21/slim'})


def main():

    parser = argparse.ArgumentParser(description='Convert MARC21 Classification to SKOS/RDF')
    parser.add_argument('infile', nargs=1, help='Input XML file')
    parser.add_argument('outfile', nargs=1, help='Output RDF file')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='More verbose output')
    parser.add_argument('-o', '--outformat', dest='outformat', nargs='?',
                        help='Output serialization format. Any format supported by rdflib. Default: turtle',
                        default='turtle')

    args = parser.parse_args()

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    in_file = args.infile[0]
    out_file = args.outfile[0]
    out_format = args.outformat

    nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}

    logger.info('Parsing: %s', in_file)
    try:
        doc = etree.parse(in_file)
    except etree.XMLSyntaxError:
        type, message, traceback = sys.exc_info()
        print "XML parsing failed"

    logger.debug('Building parent lookup table')
    parent_table = {}
    for field in doc.xpath('/mx:collection/mx:record', namespaces=nsmap):
        res = get_parent(field, nsmap)
        if res:
            parent_table[res[0]] = res[1]

    logger.debug('Traversing records')
    for record in doc.xpath('/mx:collection/mx:record', namespaces=nsmap):
        res = process_record(record, parent_table, nsmap)
        if res is not None:
            if res not in counts:
                counts[res] = 0
            counts[res] += 1

    logger.info('Found:')
    for k, v in counts.items():
        logger.info(' - %d %s', v, k)

    g.serialize(out_file, format=out_format)
    logger.info('Wrote RDF: %s', out_file)
