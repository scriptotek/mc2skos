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
from rdflib import URIRef, RDFS, Literal, Graph, BNode

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
        '23no': {
            'ns': Namespace('http://ddc23no/'),
            'same_as': 'http://dewey.info/class/{class_no}/e23/'
        }
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
    cp = get_parent(rec, nsmap)
    if not cp:
        return 'records missing 153 field'

    f153 = rec.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)[0]

    # $a - Classification number--single number or beginning number of span (R)
    class_no = cp[0]
    parent = cp[1]
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
    elif 'ess=i2' in ess:
        # Standard subdivision info? These records miss 153 $j as well and are not
        # part of the classification scheme tree.
        logger.debug('Ignoring record having $9 ess=i2: %s', class_no)
        return 'records having $9 ess=i2'

    # $j - Caption (NR)
    try:
        out['caption'] = f153.xpath('mx:subfield[@code="j"]/text()[1]', namespaces=nsmap)[0]
    except IndexError:
        pass  # Build number without caption, that's ok
        # print etree.tounicode(f153, pretty_print=True)
        # return 'missing 153 $j'

    # $e - Classification number hierarchy--single number or beginning number of span (R)
    try:
        p = parent_table[class_no]
        out['parents'].append(p)
    except KeyError:
        pass
        logger.error('Failed to find parent for: %s', class_no)
        # sys.exit(1)
        # return 'records where parents could not be found'

    # Generate URI
    try:
        scheme = classification_schemes[out['scheme']][out['edition']]
    except:
        logger.error('Unknown class scheme or edition (%s %s) for %s', out['scheme'], out['edition'], class_no)
        raise

    # Appended / is necessary for dewey.info URLs to be dereferable
    uri = scheme['ns'][out['class_no']]

    existing = [x for x in g.triples((uri, None, None))]
    if len(existing) != 0:
        logger.warning('Duplicate records for %s', out['class_no'])
        return 'duplicate records'
        # sys.exit(1)

    # Strictly, we do not need to explicitly state here that <A> and <B> are instances
    # of skos:Concept, because such statements are entailed by the definition
    # of skos:semanticRelation.
    g.add((uri, RDF.type, SKOS.Concept))
    g.add((uri, OWL.sameAs, URIRef(scheme['same_as'].format(class_no=class_no))))

    # Add caption as skos:prefLabel
    if 'caption' in out:
        g.add((uri, SKOS.prefLabel, Literal(out['caption'], lang='nb')))

    # Add classification number as skos:notation
    if 'class_no' in out:
        g.add((uri, SKOS.notation, Literal(out['class_no'])))

    # Add hierarchy as skos:broader
    for parent in out['parents']:
        if parent != out['class_no']:
            g.add((uri, SKOS.broader, scheme['ns'][parent]))

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
                g.add((uri, WD.variantName, Literal(t.capitalize(), lang='nb')))
        elif 'nch' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.classHere, Literal(t.capitalize(), lang='nb')))
        elif 'nin' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.including, Literal(t.capitalize(), lang='nb')))
        elif 'nph' in ess:
            for t in entry.xpath('mx:subfield[@code="t"]/text()', namespaces=nsmap):
                g.add((uri, WD.formerName, Literal(t.capitalize(), lang='nb')))

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

    # 765 : Synthesized Number Components
    components = []
    for syn in reversed(list(rec.xpath('mx:datafield[@tag="765"]', namespaces=nsmap))):
        g.add((uri, WD.synthesized, Literal(True)))
        uval = syn.xpath('mx:subfield[@code="u"]/text()', namespaces=nsmap)
        if len(uval) == 0:
            logger.debug("Built number without components specified: %s", class_no)
        table = ''
        rootno = ''

        wval = syn.xpath('mx:subfield[@code="w"]/text()', namespaces=nsmap)
        if len(wval) != 0:
            continue  # appears to be duplicates -- check!

        for sf in syn.xpath('mx:subfield', namespaces=nsmap):
            if sf.get('code') == 'b':    # Base number
                if len(components) == 0:
                    components.append(sf.text)
            elif sf.get('code') == 'r':    # Root number
                rootno = sf.text
            elif sf.get('code') == 'z':    # Table identification
                table = 'T{}--'.format(sf.text)
            # elif sf.get('code') == 't':    # Digits added from internal subarrangement or add table
            #     components.append(sf.text)
            elif sf.get('code') == 's':  # Digits added from classification number in schedule or external table
                if table != '':
                    components.append(table + sf.text)
                elif rootno != '':
                    sep = '.' if len(rootno) == 3 else ''
                    components.append(rootno + sep + sf.text)
            # elif sf.get('code') not in ['9', 'u']:
            #     print sf.get('code'), sf.text, class_no

    for idx, value in enumerate(components):
        compnode = BNode()
        g.add((uri, WD.component, compnode))
        g.add((compnode, WD['index'], Literal(idx + 1)))
        g.add((compnode, WD.notation, Literal(value)))

    return 'valid records'


def get_parent(node, nsmap):

    node = node.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)
    if len(node) == 0:
        return

    parts = ['', '', '', '']
    codes = ['a', 'c', 'e', 'f']
    table = ''

    for sf in node[0].xpath('mx:subfield', namespaces=nsmap):

        if sf.get('code') == 'z':
            table = 'T{}--'.format(sf.text)

        elif sf.get('code') in codes:
            i = codes.index(sf.get('code'))
            if parts[i] == '':
                parts[i] = table + sf.text
                table = ''
            else:
                parts[i] = '{}:{}'.format(parts[i], sf.text)

    current = parts[0] if parts[1] == '' else parts[0] + '-' + parts[1]
    parent = parts[2] if parts[3] == '' else parts[2] + '-' + parts[3]

    if current == '' or parent == '':
        return

    if len(node) != 1:
        logger.warning('Record has multiple 153 fields: %s', current)

    return [current, parent]

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
