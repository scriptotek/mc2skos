# encoding=utf-8
import unittest
import pytest
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import SKOS

from mc2skos.mc2skos import process_records
from mc2skos.reader import MarcFileReader
from mc2skos.vocabularies import Vocabularies

BK = Namespace('http://uri.gbv.de/terminology/bk/')


with open('mc2skos/vocabularies.yml') as fp:
    vocabularies = Vocabularies()
    vocabularies.load_yaml(fp)


def test_skosify():
    marc = MarcFileReader('examples/bk-54.65.xml')
    rdf = process_records(marc.records(), expand=True, vocabularies=vocabularies)

    assert (BK['54'], SKOS.narrower, BK['54.65']) in rdf
