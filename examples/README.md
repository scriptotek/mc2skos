The MARCXML files in this directory include examples given in appendix B of
[MARC 21 Classification format specification](https://www.loc.gov/marc/classification/):

* [class 003](https://www.loc.gov/marc/classification/examples.html#ddc003): `ddc21en-003.*.xml`
* [table 6](https://www.loc.gov/marc/classification/examples.html#ddc6): `ddc21en-6--*.xml`

Additional sample records have been added to test features not included in the official examples.

* `ddc23de-*.xml`: German WebDewey 23rd edition
* `ddc23no-*.xml`: Norwegian WebDewey 23rd edition
* `bk-*.xml`: Basisklassifikation (BK)
* `lcsh-*.xml`: [Library of Congress Subject Headings](http://id.loc.gov/)
* `bk-*.xml`: [Basisklassifikation](http://uri.gbv.de) (BK)
* `humord-*.xml: [Humord](http://data.ub.uio.no), `noubomn-*.xml: [Realfagstermer](http://data.ub.uio.no), `usvd-*.xml: [UBO index to Dewey](http://data.ub.uio.no)
* `nalt-*.xml`: [NAL Thesaurus](https://agclass.nal.usda.gov/download.shtml)
* ...

For each MARCXML file there is a corresponding RDF/Turtle file with triples expected to be included
when converting to SKOS. See `test/test_process_examples.py` for implementation.
