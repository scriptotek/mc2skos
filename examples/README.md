The MARCXML files in this directory include examples given in appendix B of
[MARC 21 Classification format specification](https://www.loc.gov/marc/classification/):

* [class 003](https://www.loc.gov/marc/classification/examples.html#ddc003): `ddc21en-003.*.xml`
* [table 6](https://www.loc.gov/marc/classification/examples.html#ddc6): `ddc21en-6--*.xml`

Additional sample records have been added to test features not included in the official examples.

* Other language and edition than DDC 21st: `ddc23de-*.xml` 
* ...

For each MARCXML file there is a corresponding RDF/Turtle file with triples expected to be included
when converting to SKOS. See `tests/test_process_examples.py` for implementation.
