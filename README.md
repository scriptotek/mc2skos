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

### Mapping schema

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

#### Classification number spans

Records that hold classification number spans (given by 153 $e and 153 $f) are not converted.
If a record has a number span as its parent, we traverse the tree upwards until we
reach a record which is not a number span, marking that record as the parent.

#### Additional processing for data from WebDewey

The script is supposed to work with any MARC21 classification data, but also supports the non-standard `ess` codes supplied in WebDewey data to differentiate between different types of notes.

| MARC21XML                                                  | RDF                                                                                                                            |
|------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `680` having `$9 ess=ndf` Definition note                  | `skos:definition`                                                                                                              |
| `680` having `$9 ess=nvn` Variant name note                | `wd:variantName` for each subfield `$t`                                                                                        |
| `680` having `$9 ess=nch` Class here note                  | `wd:classHere` for each subfield `$t`                                                                                          |
| `680` having `$9 ess=nin` Including note                   | `wd:including` for each subfield `$t`                                                                                          |
| `680` having `$9 ess=nph` Former heading                   | `wd:formerHeading` for each subfield `$t`                                                                                      |
| `685` having `$9 ess=ndn` Deprecation note                 | `owl:deprecated true`                                                                                                          |

**Notes that are currently not treated in any special way:**

* `253` having `$9 ess=nsx` Do-not-use.
* `253` having `$9 ess=nce` Class-elsewhere
* `253` having `$9 ess=ncw` Class-elsewhere-manual
* `253` having `$9 ess=nse` See.
* `253` having `$9 ess=nsw` See-manual.
* `353` having `$9 ess=nsa` See-also
* `683` having `$9 ess=nbu` Preference note
* `683` having `$9 ess=nop` Options note
* `683` having `$9 ess=non` Options note
* `684` having `$9 ess=nsm` Manual note
* `685` having `$9 ess=ndp` Discontinued partial
* `685` having `$9 ess=nrp` Relocation
* `689` having `$9 ess=nru` Sist brukt i...
