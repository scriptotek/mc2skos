# encoding=utf8
import logging
import time
from lxml import etree

logger = logging.getLogger(__name__)


class MarcFileReader:
    """Read records from a MARC XML file."""

    def __init__(self, name):
        self.name = name

    def records(self):
        logger.info('Parsing: %s', self.name)
        n = 0
        t0 = time.time()
        record_tag = '{http://www.loc.gov/MARC21/slim}record'
        for _, record in etree.iterparse(self.name, tag=record_tag):
            yield record
            record.clear()
            n += 1
            if n % 500 == 0:
                logger.info('Read %d records (%.f recs/sec)', n, (float(n) / (time.time() - t0)))
