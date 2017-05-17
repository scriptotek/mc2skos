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
and
`MARC 21 Authority <http://www.loc.gov/marc/authority/>`_
records (serialized as MARCXML) to
`SKOS <http://www.w3.org/2004/02/skos/>`_ concepts.

Developed to support the
project "`Felles terminologi for klassifikasjon med Dewey <https://www.duo.uio.no/handle/10852/39834>`_",
for converting Dewey Decimal Classification (DDC) records.
`Issues <https://github.com/scriptotek/mc2skos/issues>`_ and
suggestions for generalizations and improvements are welcome!

Installation
============

Releases can be installed from the command line with `pip <https://pip.pypa.io/>`__:

.. code-block:: console

    $ pip install --upgrade mc2skos             # with virtualenv or as root
    $ pip install --upgrade --user mc2skos      # install to ~/.local

* Works with both Python 2.x and 3.x. See `Travis <https://travis-ci.org/scriptotek/mc2skos>`_
  for details on tested Python versions.
* If lxml fails to install on Windows, try the windows installer
  from `from PyPI <https://pypi.python.org/pypi/lxml/3.4.0>`_.
* If lxml fails to install on Unix, install system packages python-dev and libxml2-dev
* Make sure the Python scripts folder has been added to your PATH.

To directly use a version from source code repository:

.. code:: console

    $ git clone https://github.com/scriptotek/mc2skos.git
    $ cd mc2skos
    $ pip install -e .

Usage
=====

.. code-block:: console

    mc2skos infile.xml outfile.ttl      # from file to file
    mc2skos infile.xml > outfile.ttl    # from file to standard output

Run ``mc2skos --help`` or ``mc2skos -h`` for options.

URIs
====

URIs are generated automatically for known concept schemes, identified from
``084 $a`` for classification records and from ``008[11]`` / ``040 $f`` for
authority records. To list known concept schemes:

.. code:: console

    $ mc2skos -l

The list is currently quite short, but pull requests for adding additional
schemes are welcome! See ``default_uri_templates`` in ``record.py``.

URIs can be also be generated on the fly from an URI template specified with option
``--uri``.  The following template parameters are recognized:

* ``{control_number}`` is the 001 value
* ``{collection}`` is "class", "table" or "scheme"
* ``{object}`` is a member of the classification scheme and part of
  a ``{collection}``, such as a specific class or table.
* ``{edition}`` is taken from ``084 $c`` (with language code stripped)


To add ``skos:inScheme`` statements to all records, an URI template can be
specified with option ``--scheme``. Otherwise, it will be derived from a default
template if the concept scheme is known.

To add an additional ``skos:inScheme`` statement to table records, an URI
template can be specified with option ``--table_scheme``. Otherwise, it will be
derived from a default template if the concept scheme is known.

The following example is generated from a DDC table record:

.. code-block:: turtle

    <http://dewey.info/class/6--982/e21/> a skos:Concept ;
        skos:inScheme <http://dewey.info/scheme/edition/e21/>,
                      <http://dewey.info/table/6/e21/> ;
        skos:notation "T6--982" ;
        skos:prefLabel "Chibchan and Paezan languages"@en .


Mapping schema for MARC21 Classification
========================================

Only a small part of the MARC21 Classification data model is converted, and the
conversion follows a rather pragmatic approach, exemplified by the mapping of
the 7XX fields to skos:altLabel.

==========================================================  =====================================
MARC21XML                                                    RDF
==========================================================  =====================================
``005`` Date and time of latest transaction                 ``dcterms:modified``
``008[0:6]`` Date entered on file                           ``dcterms:created``
``008[8]="d" or "e"`` Classification validity               ``owl:deprecated``
``153 $a``, ``$c``, ``$z`` Classification number            ``skos:notation``
``153 $j`` Caption                                          ``skos:prefLabel``
``153 $e``, ``$f``, ``$z`` Classification number hierarchy  ``skos:broader``
``253`` Complex See Reference                               ``skos:editorialNote``
``353`` Complex See Also Reference                          ``skos:editorialNote``
``680`` Scope Note                                          ``skos:scopeNote``
``683`` Application Instruction Note                        ``skos:editorialNote``
``685`` History Note                                        ``skos:historyNote``
``700`` Index Term-Personal Name                            ``skos:altLabel``
``710`` Index Term-Corporate Name                           ``skos:altLabel``
``711`` Index Term-Meeting Name                             ``skos:altLabel``
``730`` Index Term-Uniform Title                            ``skos:altLabel``
``748`` Index Term-Chronological                            ``skos:altLabel``
``750`` Index Term-Topical                                  ``skos:altLabel``
``751`` Index Term-Geographic Name                          ``skos:altLabel``
``753`` Index Term-Uncontrolled                             ``skos:altLabel``
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
            <http://dewey.info/class/1--09/e23/>
            <http://dewey.info/class/2--73/e23/>
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


Mapping schema for MARC21 Authority
========================================

Only a small part of the MARC21 Authority data model is converted.

==========================================================  =====================================
MARC21XML                                                    RDF
==========================================================  =====================================
``005`` Date and time of latest transaction                 ``dcterms:modified``
``008[0:6]`` Date entered on file                           ``dcterms:created``
``100`` Heading - Personal Name                             ``skos:prefLabel``
``110`` Heading - Corporate Name                            ``skos:prefLabel``
``111`` Heading - Meeting Name                              ``skos:prefLabel``
``130`` Heading - Uniform Title                             ``skos:prefLabel``
``147`` Heading - Named Event                               ``skos:prefLabel``
``148`` Heading - Chronological Term                        ``skos:prefLabel``
``150`` Heading - Topical Term                              ``skos:prefLabel``
``151`` Heading - Geographic Name                           ``skos:prefLabel``
``155`` Heading - Genre/Form Term                           ``skos:prefLabel``
``162`` Heading - Medium of Performance Term                ``skos:prefLabel``
``400`` See From Tracing - Personal Name                    ``skos:altLabel``
``410`` See From Tracing - Corporate Name                   ``skos:altLabel``
``411`` See From Tracing - Meeting Name                     ``skos:altLabel``
``430`` See From Tracing - Uniform Title                    ``skos:altLabel``
``447`` See From Tracing - Named Event                      ``skos:altLabel``
``448`` See From Tracing - Chronological Term               ``skos:altLabel``
``450`` See From Tracing - Topical Term                     ``skos:altLabel``
``451`` See From Tracing - Geographic Name                  ``skos:altLabel``
``455`` See From Tracing - Genre/Form Term                  ``skos:altLabel``
``462`` See From Tracing - Medium of Performance Term       ``skos:altLabel``
``500`` See Also From Tracing - Personal Name               ``skos:related`` or `skos:broader`` (see below)
``510`` See Also From Tracing - Corporate Name              ``skos:related`` or `skos:broader`` (see below)
``511`` See Also From Tracing - Meeting Name                ``skos:related`` or `skos:broader`` (see below)
``530`` See Also From Tracing - Uniform Title               ``skos:related`` or `skos:broader`` (see below)
``547`` See Also From Tracing - Named Event                 ``skos:related`` or `skos:broader`` (see below)
``548`` See Also From Tracing - Chronological Term          ``skos:related`` or `skos:broader`` (see below)
``550`` See Also From Tracing - Topical Term                ``skos:related`` or `skos:broader`` (see below)
``551`` See Also From Tracing - Geographic Name             ``skos:related`` or `skos:broader`` (see below)
``555`` See Also From Tracing - Genre/Form Term             ``skos:related`` or `skos:broader`` (see below)
``562`` See Also From Tracing - Medium of Performance Term  ``skos:related`` or `skos:broader`` (see below)
``667`` Nonpublic General Note                              ``skos:editorialNote``
``670`` Source Data Found                                   ``skos:note``
``677`` Definition                                          ``skos:definition``
``678`` Biographical or Historical Data                     ``skos:note``
``680`` Public General Note                                 ``skos:note``
``681`` Subject Example Tracing Note                        ``skos:example``
``682`` Deleted Heading Information                         ``skos:changeNote``
``688`` Application History Note                            ``skos:historyNote``
==========================================================  =====================================

Generating ``skos:related`` and ``skos:broader``
------------------------------------------------

``skos:related`` and ``skos:broader`` is currently only generated from 5XX fields
if the fields contain a ``$0`` subfield containing either the control number or the
URI of the related record.


