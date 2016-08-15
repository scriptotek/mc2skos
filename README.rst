.. image:: https://img.shields.io/travis/scriptotek/mc2skos.svg
   :target: https://travis-ci.org/scriptotek/mc2skos
   :alt: Build status

.. image:: https://img.shields.io/codecov/c/github/scriptotek/mc2skos.svg
   :target: https://codecov.io/gh/scriptotek/mc2skos
   :alt: Test coverage

.. image:: https://landscape.io/github/scriptotek/mc2skos/master/landscape.svg?style=flat
   :target: https://landscape.io/github/scriptotek/mc2skos/master
   :alt: Code health

.. image:: https://img.shields.io/pypi/v/mc2skos.svg
   :target: https://pypi.python.org/pypi/mc2skos
   :alt: Latest version

.. image:: https://img.shields.io/github/license/scriptotek/mc2skos.svg
   :target: http://opensource.org/licenses/MIT
   :alt: MIT license

Python script for converting
`MARC 21 Classification <http://www.loc.gov/marc/classification/>`_
records (serialized as MARCXML) to
`SKOS <http://www.w3.org/2004/02/skos/>`_ concepts.

Developed to support the
project "`Felles terminologi for klassifikasjon med Dewey <http://www.ub.uio.no/om/prosjekter/deweymapping/index.html>`_",
it has only been tested with Dewey Decimal Classification (DDC) records.
`Issues <https://github.com/scriptotek/mc2skos/issues>`_ and
suggestions for generalizations and improvements are welcome!

Installation
============

Using `Pip <http://pip.readthedocs.org/en/latest/installing.html>`_:

.. code-block:: console

    $ pip install -U git+https://github.com/scriptotek/mc2skos.git

* Works with both Python 2.x and 3.x. See `Travis <https://travis-ci.org/scriptotek/mc2skos>`_
  for details on tested Python versions.
* If lxml fails to install on Windows, try the windows installer
  from `from PyPI <https://pypi.python.org/pypi/lxml/3.4.0>`_.
* Make sure the Python scripts folder has been added to your PATH.

Usage example
=============

.. code-block:: console

    mc2skos infile.xml outfile.ttl

Run ``mc2skos -h`` for options.

URIs
====

For records with ``084 $a == "ddc"``, URIs are generated on the form
``http://dewey.info/{collection}/{object}/e{edition}/``, where
``{collection}`` is "class", "table" or "scheme", and ``{edition}`` is
taken from ``084 $c`` (with language code stripped).

.. code-block:: turtle

    <http://dewey.info/class/6--982/e21/> a skos:Concept ;
        skos:inScheme <http://dewey.info/scheme/edition/e21/>,
            <http://dewey.info/table/6/e21/> ;
        skos:notation "T6--982" ;
        skos:prefLabel "Chibchan and Paezan languages"@en .

To override this, you can specify ``--uri`` to set a URI template for classes and table record,
``--scheme`` to set a URI to be used with ``skos:inScheme`` for all records, and ``--table_scheme``
to set a URI template to be used with ``skos:inScheme`` for table records. Note that
if ``--uri`` is specified, but not ``--scheme``, no ``skos:inScheme`` will be added. Same goes
with ``--table_scheme``.

Mapping schema
==============

Only a small part of the MARC21 Classification
data model is converted, and the conversion follows a rather
pragmatic approach, exemplified by the mapping of the 7XX fields
to skos:altLabel.

==========================================================  =====================================
MARC21XML                                                    RDF
==========================================================  =====================================
``153 $a``, ``$c``, ``$z`` Classification number            ``skos:notation``
``153 $j`` Caption                                          ``skos:prefLabel``
``153 $e``, ``$f``, ``$z`` Classification number hierarchy  ``skos:broader``
``253`` Complex See Reference                               ``skos:editorialNote``
``353`` Complex See Also Reference                          ``skos:editorialNote``
``680`` Scope Note                                          ``skos:scopeNote``
``683`` Application Instruction Note                        ``skos:editorialNote``
``685`` History Note                                        ``skos:historyNote``
``694`` ??? Note                                            ``skos:editorialNote``
``700`` Index Term-Personal Name                            ``skos:altLabel``
``710`` Index Term-Corporate Name                           ``skos:altLabel``
``711`` Index Term-Meeting Name                             ``skos:altLabel``
``730`` Index Term-Uniform Title                            ``skos:altLabel``
``748`` Index Term-Chronological                            ``skos:altLabel``
``750`` Index Term-Topical                                  ``skos:altLabel``
``751`` Index Term-Geographic Name                          ``skos:altLabel``
``765`` Synthesized Number Components                       ``mads:componentList`` (see below)
==========================================================  =====================================

Synthesized number components
-----------------------------

Components of synthesized numbers explicitly described in 765 fields are
expressed using the `mads:componentList` property, and to preserve the order of the
components, we use RDF lists. Example:

.. code-block:: turtle

    @prefix mads: <http://www.loc.gov/mads/rdf/v1#> .

    <http://dewey.info/class/001.30973/e23/> a skos:Concept ;
        mads:componentList (
            <http://dewey.info/class/001.3/e23/>
            <http://dewey.info/class/T1--09/e23/>
            <http://dewey.info/class/T2--73/e23/>
        ) ;
        skos:notation "001.30973" .

Retrieving list members *in order* is `surprisingly hard <http://answers.semanticweb.com/questions/18056/querying-rdf-lists-collections-with-sparql>`_ with SPARQL.
Retrieving ordered pairs is the best solution I've come up with so far:

.. code-block::

    PREFIX mads: <http://www.loc.gov/mads/rdf/v1#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?c1_notation ?c1_label ?c2_notation ?c2_label
    WHERE { GRAPH <http://localhost/ddc23no> {

        <http://dewey.info/class/001.30973/e23/> mads:componentList ?l .
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

===========  =================================================  ===========  ===================================================
c1_notation  c1_label                                           c2_notation  c2_label
===========  =================================================  ===========  ===================================================
"001.3"      "Humaniora"@nb                                     "T1--09"     "Historie, geografisk behandling, biografier"@nb
"T1--09"     "Historie, geografisk behandling, biografier"@nb   "T2--73"     "USA"@nb
===========  =================================================  ===========  ===================================================


Additional processing for data from WebDewey
--------------------------------------------

The script is supposed to work with any MARC21 classification data, but also supports the non-standard ``ess`` codes supplied in WebDewey data to differentiate between different types of notes.

===================================================  ================================================
MARC21XML                                            RDF
===================================================  ================================================
``680`` having ``$9 ess=ndf`` Definition note        ``skos:definition``
``680`` having ``$9 ess=nvn`` Variant name note      ``wd:variantName`` for each subfield ``$t``
``680`` having ``$9 ess=nch`` Class here note        ``wd:classHere`` for each subfield ``$t``
``680`` having ``$9 ess=nin`` Including note         ``wd:including`` for each subfield ``$t``
``680`` having ``$9 ess=nph`` Former heading         ``wd:formerHeading`` for each subfield ``$t``
``685`` having ``$9 ess=ndn`` Deprecation note       ``owl:deprecated true``
``694`` having ``$9 ess=nml`` ???                    ``SKOS.editorialNote``
===================================================  ================================================

**Notes that are currently not treated in any special way:**

* ``253`` having ``$9 ess=nsx`` Do-not-use.
* ``253`` having ``$9 ess=nce`` Class-elsewhere
* ``253`` having ``$9 ess=ncw`` Class-elsewhere-manual
* ``253`` having ``$9 ess=nse`` See.
* ``253`` having ``$9 ess=nsw`` See-manual.
* ``353`` having ``$9 ess=nsa`` See-also
* ``683`` having ``$9 ess=nbu`` Preference note
* ``683`` having ``$9 ess=nop`` Options note
* ``683`` having ``$9 ess=non`` Options note
* ``684`` having ``$9 ess=nsm`` Manual note
* ``685`` having ``$9 ess=ndp`` Discontinued partial
* ``685`` having ``$9 ess=nrp`` Relocation
* ``689`` having ``$9 ess=nru`` Sist brukt i...
