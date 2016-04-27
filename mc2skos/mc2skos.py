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
import argparse
from rdflib.namespace import OWL, RDF, RDFS, SKOS, Namespace
from rdflib import URIRef, RDFS, Literal, Graph, BNode
from otsrdflib import OrderedTurtleSerializer

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
MADS = Namespace('http://www.loc.gov/mads/rdf/v1#')

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

            if txt is None:
                continue

            if c == 'c':
                note += '-'
            elif len(note) != 0 and not re.match(r'[.\?#@+,<>%~`!$^&\(\):;\]]', txt[0]):
                note += ' '
            note += txt

    return note


def get_ess(node, nsmap):
    # Get the first WebDewey 'ess' property
    return [x.replace('ess=', '') for x in node.xpath('mx:subfield[@code="9"]/text()[1]', namespaces=nsmap)]


def process_record(rec, nsmap, namespace, skos_scheme, same_as, include_indexterms=False, include_notes=False, include_components=False):
    # Parse a single MARC21 classification record
    class_no = ''

    leader = rec.xpath('mx:leader', namespaces=nsmap)[0].text
    if leader[6] != 'w':  # w: classification, z: authority
        return

    out = {'notes': [], 'scope_notes': [], 'history_notes': [], 'index_terms': []}

    # Parse 153: Classification number
    r = rec.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)
    class_no = get_classno(rec, nsmap)
    if not class_no:
        return 'records missing 153 field'

    f153 = rec.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)[0]

    # $a - Classification number--single number or beginning number of span (R)
    out['class_no'] = class_no

    # Not sure yet if we should include these, and how to represent them:
    if class_no.find(':') != -1:
        return 'records with add table notation'

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

    # Generate URI
    uri = namespace[out['class_no']]

    existing = [x for x in g.triples((uri, None, None))]
    if len(existing) != 0:
        logger.warning('Duplicate records for %s', out['class_no'])
        return 'duplicate records'
        # sys.exit(1)

    # Strictly, we do not need to explicitly state here that <A> and <B> are instances
    # of skos:Concept, because such statements are entailed by the definition
    # of skos:semanticRelation.
    g.add((uri, RDF.type, SKOS.Concept))

    # $e - Classification number hierarchy--single number or beginning number of span (R)
    parent = get_parent(rec, nsmap)
    if parent:
        if skos_scheme is not None:
            g.add((uri, SKOS.inScheme, skos_scheme))
        if parent != out['class_no']:
            g.add((uri, SKOS.broader, namespace[parent]))
    else:
        logger.info('Marking %s as topConcept', class_no)
        if skos_scheme is not None:
            g.add((uri, SKOS.topConceptOf, skos_scheme))
        # sys.exit(1)
        # return 'records where parents could not be found'

    if same_as is not None:
        g.add((uri, OWL.sameAs, URIRef(same_as.format(class_no=class_no))))

    # Add caption as skos:prefLabel
    if 'caption' in out:
        g.add((uri, SKOS.prefLabel, Literal(out['caption'], lang='nb')))

    # Add classification number as skos:notation
    if 'class_no' in out:
        if out['class_no'].find('--') != -1:
            g.add((uri, SKOS.notation, Literal('T' + out['class_no'])))
        else:
            g.add((uri, SKOS.notation, Literal(out['class_no'])))

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
    if include_notes:
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
    if include_notes:
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
    if include_notes:
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
    if include_notes:
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
    if include_notes:
        for entry in rec.xpath('mx:datafield[@tag="685"]', namespaces=nsmap):
            note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
            g.add((uri, SKOS.historyNote, Literal(note, lang='nb')))
            ess = get_ess(entry, nsmap)
            if 'ndn' in ess:
                g.add((uri, OWL.deprecated, Literal(True)))

    # 694 : ??? Note : Wrong code for 684 'Auxiliary Instruction Note' ??
    # Example:
    #   <mx:datafield tag="694" ind2=" " ind1=" ">
    #     <mx:subfield code="i">De fleste verker om seletøy og tilbehør klassifiseres med hester i</mx:subfield>
    #     <mx:subfield code="a">636.10837</mx:subfield>
    #     <mx:subfield code="9">ess=nml</mx:subfield>
    #   </mx:datafield>
    #
    if include_notes:
        for entry in rec.xpath('mx:datafield[@tag="694"]', namespaces=nsmap):
            note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
            ess = get_ess(entry, nsmap)
            if 'nml' in ess:
                g.add((uri, SKOS.editorialNote, Literal(note, lang='nb')))

    # 700 - Index Term - Personal Name (R)
    # 710 - Index Term - Corporate Name (R)
    # 711 - Index Term - Meeting Name (R)
    # 730 - Index Term - Uniform Title (R)
    # 748 - Index Term - Chronological (R)
    # 750 - Index Term - Topical (R)
    # 751 - Index Term - Geographic Name (R)
    # String order: $a : $x : $v : $y : $z
    if include_indexterms:
        for entry in rec.xpath('mx:datafield[@tag="700" or @tag="710" or @tag="711" or @tag="730" or @tag="748" or @tag="750" or @tag="751"]', namespaces=nsmap):
            term = []
            for x in ['a', 'x', 'y', 'z', 'v']:
                term.extend(entry.xpath('mx:subfield[@code="%s"]/text()' % (x), namespaces=nsmap))
            term = ' : '.join(term)

            if term == '':
                return 'records having empty index terms'
            g.add((uri, SKOS.altLabel, Literal(term, lang='nb')))

    # 765 : Synthesized Number Components
    if include_components:
        components = []
        for syn in reversed(list(rec.xpath('mx:datafield[@tag="765"]', namespaces=nsmap))):
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
                        components.append(table + sf.text)
                        table = ''
                elif sf.get('code') == 'r':    # Root number
                    rootno = sf.text
                elif sf.get('code') == 'z':    # Table identification
                    table = '{}--'.format(sf.text)
                # elif sf.get('code') == 't':    # Digits added from internal subarrangement or add table
                #     components.append(sf.text)
                elif sf.get('code') == 's':  # Digits added from classification number in schedule or external table
                    sep = '.' if len(rootno) == 3 else ''
                    components.append(table + rootno + sep + sf.text)
                    table = ''
                # elif sf.get('code') not in ['9', 'u']:
                #     print sf.get('code'), sf.text, class_no

        if len(components) != 0:
            component = components.pop(0)
            b1 = BNode()
            g.add((uri, MADS.componentList, b1))
            g.add((b1, RDF.first, namespace[component]))

            for component in components:
                b2 = BNode()
                g.add((b1, RDF.rest, b2))
                g.add((b2, RDF.first, namespace[component]))
                b1 = b2

            g.add((b1, RDF.rest, RDF.nil))

    return 'valid records'


def get_classno(node, nsmap):
    node = node.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)
    if len(node) == 0:
        return

    table = ''
    addtable = ''
    classno = ''

    for sf in node[0].xpath('mx:subfield', namespaces=nsmap):
        code = sf.get('code')

        if code == 'z':
            table = '{}--'.format(sf.text)
        elif code == 'y':
            if sf.text == '1':
                addtable = ':'
            else:
                addtable = ':{};'.format(sf.text)
        elif code in ['a', 'c', 'e', 'f']:
            val = table + addtable + sf.text
            if code == 'a':
                classno += val
            elif code == 'c':
                classno += '-' + val
            table = ''
            addtable = ''

    if classno == '':
        return

    if len(node) != 1:
        logger.warning('Record has multiple 153 fields: %s', classno)

    return classno


def get_parent(node, nsmap):

    node = node.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)
    if len(node) == 0:
        return

    table = ''
    addtable = ''
    current = ''
    parent = ''

    for sf in node[0].xpath('mx:subfield', namespaces=nsmap):
        code = sf.get('code')

        if code == 'z':
            table = '{}--'.format(sf.text)
        elif code == 'y':
            if sf.text == '1':
                addtable = ':'
            else:
                addtable = ':{};'.format(sf.text)
        elif code in ['a', 'c', 'e', 'f']:
            val = table + addtable + sf.text
            if code == 'e':
                parent += val
            elif code == 'f':
                parent += '-' + val
            table = ''
            addtable = ''

    if parent == '':
        return

    if len(node) != 1:
        logger.warning('Record has multiple 153 fields: %s', current)

    return parent

    # node = doc.xpath('//mx:datafield[@tag="153"][count(./mx:subfield[@code="a"]) = 1 and ./mx:subfield[@code="a"] = "%s" and ./mx:subfield[@code="c"] = "%s"]' % (par1, par2),
    #                  namespaces={'mx': 'http://www.loc.gov/MARC21/slim'})


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
    parser.add_argument('outfile', nargs=1, help='Output RDF file')
    parser.add_argument('namespace', nargs=1, help='Namespace to build the URIs for the classes.')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='More verbose output')
    parser.add_argument('-o', '--outformat', dest='outformat', nargs='?',
                        help='Output serialization format. Any format supported by rdflib. Default: turtle',
                        default='turtle')

    parser.add_argument('--scheme', dest='skosScheme', help='SKOS scheme the classes should be part of.')
    parser.add_argument('--sameas', dest='sameAs', help='Template for sameAs URIs.')
    parser.add_argument('--prefix', dest='prefix', help='Namespace prefix.')

    parser.add_argument('--indexterms', dest='indexterms', action='store_true', help='Include index terms from 7XX.')
    parser.add_argument('--notes', dest='notes', action='store_true', help='Include note fields.')
    parser.add_argument('--components', dest='components', action='store_true', help='Include component information from 765.')

    args = parser.parse_args()

    ns1 = Namespace(args.namespace[0])
    DCT = Namespace('http://purl.org/dc/terms/')
    nm = g.namespace_manager
    nm.bind('dct', DCT)
    nm.bind('skos', SKOS)
    nm.bind('wd', WD)
    nm.bind('mads', MADS)
    nm.bind('owl', OWL)
    if args.prefix:
        nm.bind('ddc', ns1)

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    in_file = args.infile[0]
    out_file = args.outfile[0]
    out_format = args.outformat

    nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}

    # logger.info('Parsing: %s', in_file)
    # try:
    #     doc = etree.parse(in_file)
    # except etree.XMLSyntaxError:
    #     type, message, traceback = sys.exc_info()
    #     print "XML parsing failed"
    options = {
        'namespace': ns1,
        'skos_scheme': args.skosScheme,
        'same_as': args.sameAs,
        'include_indexterms': args.indexterms,
        'include_notes': args.notes,
        'include_components': args.components
    }

    if options['skos_scheme'] is not None:
        options['skos_scheme'] = URIRef(options['skos_scheme'])

    logger.debug('Traversing records')
    n = 0
    t0 = time.time()
    for record in get_records(in_file):
        res = process_record(record, nsmap, **options)
        # if res is not None:
        #     if res not in counts:
        #         counts[res] = 0
        #     counts[res] += 1

    logger.info('Found:')
    for k, v in counts.items():
        logger.info(' - %d %s', v, k)

    s = OrderedTurtleSerializer(g)
    s.sorters = {
      'http://dewey.info/class/([0-9.]+)': lambda x: float(x[0]),
      'http://dewey.info/class/([0-9])\-\-([0-9]+)': lambda x: 1000. + int(x[0]) + float('.' + x[1])
    }
    s.serialize(open(out_file, 'wb'))
    logger.info('Wrote RDF: %s', out_file)
