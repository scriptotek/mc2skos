mc2skos
---

Python script for converting
[MARC 21 Classification](http://www.loc.gov/marc/classification/)
records (serialized as MARCXML) to
[SKOS](http://www.w3.org/2004/02/skos/) concepts.

Developed to support the
project *[Felles terminologi for klassifikasjon med Dewey](http://www.ub.uio.no/om/prosjekter/deweymapping/index.html)*,
it has only been tested with Dewey Decimal Classification (DDC) records.
[Issues](https://github.com/scriptotek/mc2skos/issues) and
suggestions for generalizations and improvements are welcome!

### Installation:

Using [Pip](http://pip.readthedocs.org/en/latest/installing.html):
```
pip install git+git://github.com/scriptotek/mc2skos.git
```

* Requires Python 2.6 or 2.7. Not tested with 3.x.
* If lxml fails to install on Windows, try the windows installer
from [from PyPI](https://pypi.python.org/pypi/lxml/3.4.0).
* Make sure the Python scripts folder has been added to your PATH.

### Usage:

```bash
$ mc2skos infile.xml outfile.rdf
```

Only a small part of the MARC21 Classification
data model is converted, and the conversion follows a rather
pragmatic approach, exemplified by the mapping of
[750](http://www.loc.gov/marc/classification/cd750.html)
to skos:altLabel.

    153 $a → skos:notation
    153 $j → skos:prefLabel
    153 $e → skos:broader
    750    → skos:altLabel
    680    → skos:scopeNote
    685    → skos:historyNote
    253    → skos:editorialNote
    353    → skos:editorialNote
    683    → skos:editorialNote

Note on classification number spans:

In general, we ignore records coding classification number spans.
However, a record may have a number span as its parent (given
by 153 $e and 153 $f combined). In such cases, we traverse the tree
in reverse until we reach a record which is not a number span.
