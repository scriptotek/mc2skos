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
from lxml import etree
import argparse
from rdflib.namespace import RDF, RDFS, SKOS, Namespace
from rdflib import URIRef, RDFS, Literal, Graph

g = Graph()
dct = Namespace('http://purl.org/dc/terms/')
nm = g.namespace_manager
nm.bind('dct', 'http://purl.org/dc/terms/')
nm.bind('skos', SKOS)

classification_schemes = {
    'ddc': {
        '23no': {'ns': Namespace('http://dewey.info/class/'), 'el': '{class_no}/e23/'}
    }
}

counts = {}


def store_record(rec):
    # Add record data to graph

    scheme = classification_schemes[rec['scheme']][rec['edition']]

    # Appended / is necessary for dewey.info URLs to be dereferable
    uri = scheme['ns'][scheme['el'].format(class_no=rec['class_no'])]

    existing = [x for x in g.triples((uri, None, None))]
    if len(existing) != 0:
        print "ERROR: Duplicate records for %s" % (rec['class_no'])
        print rec
        for t in existing:
            print t

        return
        # sys.exit(1)

    # We do not need to explicitly state here that <A> and <B> are instances
    # of skos:Concept, because such statements are entailed by the definition
    # of skos:semanticRelation.
    # g.add((uri, RDF.type, SKOS.Concept))

    # Add caption as prefLabel
    if 'caption' in rec:
        g.add((uri, SKOS.prefLabel, Literal(rec['caption'], lang='nb')))

    # Add index terms as altLabels
    for index_term in rec['index_terms']:
        if 'caption' not in rec or index_term != rec['caption']:
            g.add((uri, SKOS.altLabel, Literal(index_term, lang='nb')))

    # Add hierarchy
    # Add classification number as skos:notation
    if 'class_no' in rec:
        g.add((uri, SKOS.notation, Literal(rec['class_no'])))

    if 'parent' in rec:
        parent = rec['parent']
        if parent != rec['class_no']:
            g.add((uri, SKOS.broader, scheme['ns'][scheme['el'].format(class_no=parent)]))

    # Add scope notes
    for scope_note in rec['scope_notes']:
        g.add((uri, SKOS.scopeNote, Literal(scope_note, lang='nb')))

    # Add notes
    for note in rec['notes']:
        g.add((uri, SKOS.editorialNote, Literal(note, lang='nb')))


def stringify(nodes):
    note = ''
    for subfield in nodes:
        c = subfield.get('code')
        if c == 'i' or c == 't' or c == 'a':
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
            note += txt
            if c == 'i' or c == 't':
                note += ' '
    return note


def process_record(rec, parent_table, nsmap):
    # Parse a single MARC21 classification record

    leader = rec.xpath('mx:leader', namespaces=nsmap)[0].text
    if leader[6] != 'w':  # w: classification, z: authority
        return

    out = {}

    # 084: Classification Scheme and Edition
    r = rec.xpath('mx:datafield[@tag="084"]', namespaces=nsmap)
    if not r:
        return 'missing 084 field'
    f084 = r[0]
    scheme = [x for x in f084.xpath('mx:subfield[@code="a"]/text()', namespaces=nsmap)]
    edt = [x for x in f084.xpath('mx:subfield[@code="c"]/text()', namespaces=nsmap)]
    if len(scheme) != 1 or len(edt) != 1:
        # print 'Warning: Ignore records with multiple classification numbers', class_no
        return 'classification scheme or edition missing'
    out['scheme'] = scheme[0]
    out['edition'] = edt[0]

    # 153: Classification number
    r = rec.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)
    if not r:
        return 'missing 153 field'
    f153 = r[0]

    # $a - Classification number--single number or beginning number of span (R)
    class_no = [x for x in f153.xpath('mx:subfield[@code="a"]/text()', namespaces=nsmap)]
    if len(class_no) != 1:
        # print 'Warning: Ignore records with multiple classification numbers', class_no
        return 'numbers with colon'
    out['class_no'] = class_no[0]

    # $c - Classification number--ending number of span (R)
    endnumber = [x for x in f153.xpath('mx:subfield[@code="c"]/text()[1]', namespaces=nsmap)]
    if len(endnumber) != 0:
        # This record representes a span. We skip such records
        # print 'Skipping span: ', class_no, endnumber
        return 'classification number span'

    # $e - Parent
    parent = [x for x in f153.xpath('mx:subfield[@code="e"]/text()[1]', namespaces=nsmap)]
    if len(parent) == 0:
        return 'no parent'

    # $j - Caption (NR)
    try:
        out['caption'] = f153.xpath('mx:subfield[@code="j"]/text()[1]', namespaces=nsmap)[0]
    except IndexError:
        pass  # Build number without caption
        # print etree.tounicode(f153, pretty_print=True)
        # return 'missing 153 $j'

    # $e - Classification number hierarchy--single number or beginning number of span (R)
    if out['class_no'] in parent_table:
        out['parent'] = parent_table[out['class_no']]
        while out['parent'].find('-') != -1:
            # print 'parent of ', out['parent'], ' is ', parent_table[out['parent']]
            out['parent'] = parent_table[out['parent']]
    else:
        print 'ERROR: Has no parent', out['class_no']

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
    out['notes'] = []
    for entry in rec.xpath('mx:datafield[@tag="253"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        out['notes'].append(note)

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
    out['scope_notes'] = []
    for entry in rec.xpath('mx:datafield[@tag="680"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        out['scope_notes'].append(note)

    # 685 : History note
    # Example:
    #  <mx:datafield tag="685" ind2="0" ind1="1">
    #    <mx:subfield code="i">Klassifiseres nå i</mx:subfield>
    #    <mx:subfield code="a">512.901</mx:subfield>
    #    <mx:subfield code="c">512.909</mx:subfield>
    #    <mx:subfield code="9">ess=nrl</mx:subfield>
    #  </mx:datafield>
    #
    out['history_notes'] = []
    for entry in rec.xpath('mx:datafield[@tag="685"]', namespaces=nsmap):
        note = stringify(entry.xpath('mx:subfield', namespaces=nsmap))
        out['history_notes'].append(note)

    # 750 : Index term
    # String order: $a : $x : $v : $y : $z
    out['index_terms'] = []
    for entry in rec.xpath('mx:datafield[@tag="750"]', namespaces=nsmap):
        term = []
        for x in ['a', 'x', 'y', 'z']:
            term.extend(entry.xpath('mx:subfield[@code="%s"]/text()' % (x), namespaces=nsmap))
        term = ' : '.join(term)

        if term == '':
            return 'empty_750'
        out['index_terms'].append(term)

    # Add to graph
    store_record(out)
    return 'valid'


def get_parent(node, nsmap):

    node = node.xpath('mx:datafield[@tag="153"]', namespaces=nsmap)

    if len(node) != 1:
        return

    node = node[0]

    class_no1 = node.xpath('mx:subfield[@code="a"]/text()[1]', namespaces=nsmap)
    if len(class_no1) == 0:
        return
    class_no1 = class_no1[0]

    class_no2 = node.xpath('mx:subfield[@code="c"]/text()[1]', namespaces=nsmap)
    if len(class_no2) == 0:
        class_no = class_no1
    else:
        class_no = '%s-%s' % (class_no1, class_no2[0])

    ch = node.xpath('mx:subfield[@code="a"]', namespaces=nsmap)
    if len(ch) != 1:
        # print etree.tounicode(node)
        return  # ignore add table notation

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
    parser.add_argument('-o', '--outformat', dest='outformat', nargs='?',
                        help='Output serialization format. Any format supported by rdflib. Default: turtle',
                        default='turtle')

    args = parser.parse_args()

    in_file = args.infile[0]
    out_file = args.outfile[0]
    out_format = args.outformat

    nsmap = {'mx': 'http://www.loc.gov/MARC21/slim'}

    print "Parsing: %s" % (in_file)
    try:
        doc = etree.parse(in_file)
    except etree.XMLSyntaxError:
        type, message, traceback = sys.exc_info()
        print "XML parsing failed"

    print "Building parent lookup table"
    parent_table = {}
    for field in doc.xpath('/mx:collection/mx:record', namespaces=nsmap):
        res = get_parent(field, nsmap)
        if res:
            parent_table[res[0]] = res[1]

    print "Traversing records"
    for record in doc.xpath('/mx:collection/mx:record', namespaces=nsmap):
        res = process_record(record, parent_table, nsmap)
        if res is not None:
            if res not in counts:
                counts[res] = 0
            counts[res] += 1

    print "Found:"
    for k, v in counts.items():
        print ' - %s: %d' % (k, v)

    g.serialize(out_file, format=out_format)
    print "Wrote RDF: %s" % (out_file)
