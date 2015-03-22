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

In cases where the components of synthesized numbers are explicitly
noted using 765 fields, these are related to the class itself using
the `wd:component` property. To preserve the order of the components,
each component becomes a blank node with increasing index (`wd.index`)
starting on 1. Blank nodes are used since we really don't want to generate
URIs for each component. Example:

```
<http://ddc23no/T1--0112> a skos:Concept ;
    wd:component [ wd:class <http://ddc23no/003.2> ;
            wd:index 2 ],
        [ wd:class <http://ddc23no/T1--011> ;
            wd:index 1 ] ;
    wd:synthesized true ;
    owl:sameAs <http://dewey.info/class/T1--0112/e23/> ;
    skos:broader <http://ddc23no/T1--011> ;
    skos:notation "T1--0112" .
```

To retrieve the ordered components:

```sparql
PREFIX wd: <http://data.ub.uio.no/webdewey-terms#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?class_notation ?idx ?component_notation ?component_heading
WHERE { GRAPH <http://localhost/ddc23no> {
    <http://ddc23no/T1--0112> skos:notation ?class_notation ;
                              wd:component ?bnode .
    ?bnode wd:index ?idx ;
           wd:class ?component_uri .
    OPTIONAL {
        ?component_uri skos:notation ?component_notation ;
                       skos:prefLabel ?component_heading .
    }
    OPTIONAL {
        ?component_uri  skos:prefLabel ?component_heading .
    }
}}
ORDER BY ?idx
```

| class_notation | idx | component_notation | component_heading           |
|----------------|-----|--------------------|-----------------------------|
| "T1--0112"     | 1   | "T1--011"          | "Systemer"@nb               |
| "T1--0112"     | 2   | "003.2"            | "Prognoser og scenarier"@nb |

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
