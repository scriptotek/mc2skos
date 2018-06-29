# encoding=utf8

from functools import reduce
from lxml import etree
import re


class Element(object):

    nsmap = {
        'mx': 'http://www.loc.gov/MARC21/slim',
        'marc': 'http://www.loc.gov/MARC21/slim',
    }

    def __init__(self, data):
        if isinstance(data, etree._Element):
            self.node = data
        else:
            self.node = etree.fromstring(data)

    def get(self, name):
        return self.node.get(name)

    def all(self, xpath):
        # Yields all nodes matching the xpath
        for res in self.node.xpath(xpath, namespaces=self.nsmap):
            yield Element(res)

    def first(self, xpath):
        # Returns first node or None
        for res in self.all(xpath):
            return res

    def text(self, xpath=None, all=False):
        # xpath: the xpath
        # all: True to return an array with the text content for all matching elements.
        #      False to return a string with the text content of the first matching element, or None.
        # Returns text content of first node or None

        def flatten_text(node):
            # Captions can include Processing Instruction tags, like in this example
            # (linebreaks added):
            #
            #   <mx:subfield xmlns:mx="http://www.loc.gov/MARC21/slim"
            #                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" code="t">
            #     <?ddc fotag="fo:inline" font-style="italic"?>L
            #       <?ddc fotag="fo:inline" vertical-align="super" font-size="70%"?>p
            #       <?ddc fotag="/fo:inline"?>
            #     <?ddc fotag="/fo:inline"?>-rom
            #   </mx:subfield>
            #
            # The code below just strips away the PI tags, giving "Lp-rom" for this example.
            children = node.getchildren()
            if len(children) != 0:
                value = ''
                for child in children:
                    if child.tail is not None:
                        value += child.tail
            else:
                value = node.text
            return value

        if xpath is None:
            return flatten_text(self.node)
        if all:
            return [flatten_text(res.node) for res in self.all(xpath) if res.node.text is not None]
        for res in self.all(xpath):
            return flatten_text(res.node)  # return text of first element

    def get_ess_codes(self):
        return [x[4:] for x in self.node.xpath('mx:subfield[@code="9"]/text()', namespaces=self.nsmap) if x.find('ess=') == 0]

    def reduce(self, fn, subfields=['a', 'c', 'i', 't', 'x'], initializer=''):
        codes = ['@code="%s"' % code for code in subfields]
        return reduce(fn, self.all('mx:subfield[%s]' % ' or '.join(codes)), initializer)

    def stringify(self, subfields=['a', 'c', 'i', 't', 'x']):
        def inner(label, subfield):
            code = subfield.get('code')
            value = subfield.text()
            if value is None:
                return label

            # Check if we need to add a separator
            if code == 'c':
                # Treat $c as the end of a number span, which is correct for the 6XX fields
                # in MARC21 Classification. In Marc21 Authority, $c generally seems to be
                # undefined, but we might add some checks here if there are some $c subfields
                # that need to be treated differently.
                value = '-' + value

            elif len(label) != 0 and not re.match(r'[.\?#@+,<>%~`!$^&\(\):;\]]', value[0]):
                # Unless the subfield starts with a punctuation character, we will add a space.
                value = ' ' + value

            return label + value

        return self.reduce(inner, subfields)
