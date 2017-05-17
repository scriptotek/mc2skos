# encoding=utf8

import re
from lxml import etree


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
        if xpath is None:
            return self.node.text
        if all:
            return [res.node.text for res in self.all(xpath) if res.node.text is not None]
        for res in self.all(xpath):
            return res.node.text  # return text of first element

    def get_ess_codes(self):
        return [x[4:] for x in self.node.xpath('mx:subfield[@code="9"]/text()', namespaces=self.nsmap) if x.find('ess=') == 0]

    def stringify(self):
        note = ''
        for subfield in self.node.xpath('mx:subfield', namespaces=self.nsmap):
            c = subfield.get('code')
            if c in ['a', 'c', 'i', 't', 'x']:

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

                children = subfield.getchildren()
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
