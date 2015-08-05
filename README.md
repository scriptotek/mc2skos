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
$ mc2skos infile.xml outfile.rdf [--verbose]
```

### Mapping schema

Only a small part of the MARC21 Classification
data model is converted, and the conversion follows a rather
pragmatic approach, exemplified by the mapping of
[750](http://www.loc.gov/marc/classification/cd750.html)
to skos:altLabel.

Synthesized numbers are indicated by `wd:synthesized true`, but no attempt is
made to express the actual components. Note that a synthesized number may not
have a caption (and thus a `skos:prefLabel`).


| MARC21XML                                        | RDF                                  |
|--------------------------------------------------|--------------------------------------|
| `153 $a` Classification number                   | `skos:notation`                      |
| `153 $j` Caption                                 | `skos:prefLabel`                     |
| `153 $e` Classification number hierarchy         | `skos:broader`                       |
| `253` Complex See Reference                      | `skos:editorialNote`                 |
| `353` Complex See Also Reference                 | `skos:editorialNote`                 |
| `680` Scope Note                                 | `skos:scopeNote`                     |
| `683` Application Instruction Note               | `skos:editorialNote`                 |
| `685` History Note                               | `skos:historyNote`                   |
| `750` Index Term-Topical                         | `skos:altLabel`                      |
| `765` Synthesized Number Components              | `wd:synthesized true`                |


#### Synthesized number components

Components of synthesized numbers explicitly described in 765 fields are
expressed using the `wd:component` property. To preserve the order of the
components, we use RDF lists. Example:

```
<http://data.ub.uio.no/ddc/001.30973> a skos:Concept ;
    wd:component ( <http://data.ub.uio.no/ddc/001.3> <http://data.ub.uio.no/ddc/T1--09> <http://data.ub.uio.no/ddc/T2--73> ) ;
    wd:synthesized true ;
    skos:notation "001.30973" .

```

Retrieving list members *in order* is [surprisingly hard](http://answers.semanticweb.com/questions/18056/querying-rdf-lists-collections-with-sparql) with SPARQL.
This is what I've come up with so far:

```sparql
PREFIX wd: <http://data.ub.uio.no/webdewey-terms#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?c1_notation ?c1_label ?c2_notation ?c2_label
WHERE { GRAPH <http://localhost/ddc23no> {

    <http://data.ub.uio.no/ddc/001.30973> wd:component ?l .
        ?l rdf:rest* ?sl .
        ?sl rdf:first ?e1 .
        ?sl rdf:rest ?sln .
        ?sln rdf:first ?e2 .

        ?e1 skos:notation ?c1_notation .
        ?e2 skos:notation ?c2_notation .

        OPTIONAL {
            ?e1 skos:prefLabel ?c1_label .
        }
        OPTIONAL {
            ?e2 skos:prefLabel ?c2_label .
        }
}}
```

| c1_notation | c1_label                                         | c2_notation | c2_label                                         |
|-------------|--------------------------------------------------|-------------|--------------------------------------------------|
| "001.3"     | "Humaniora"@nb                                   | "T1--09"    | "Historie, geografisk behandling, biografier"@nb |
| "T1--09"    | "Historie, geografisk behandling, biografier"@nb | "T2--73"    | "USA"@nb                                         |


#### Additional processing for data from WebDewey

The script is supposed to work with any MARC21 classification data, but also supports the non-standard `ess` codes supplied in WebDewey data to differentiate between different types of notes.

| MARC21XML                                         | RDF                                           |
|---------------------------------------------------|-----------------------------------------------|
| `680` having `$9 ess=ndf` Definition note         | `skos:definition`                             |
| `680` having `$9 ess=nvn` Variant name note       | `wd:variantName` for each subfield `$t`       |
| `680` having `$9 ess=nch` Class here note         | `wd:classHere` for each subfield `$t`         |
| `680` having `$9 ess=nin` Including note          | `wd:including` for each subfield `$t`         |
| `680` having `$9 ess=nph` Former heading          | `wd:formerHeading` for each subfield `$t`     |
| `685` having `$9 ess=ndn` Deprecation note        | `owl:deprecated true`                         |

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
