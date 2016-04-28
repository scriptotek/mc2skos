#!/usr/bin/env python
# encoding=utf-8
from __future__ import print_function
import os
import sys

try:
    from setuptools import setup
except ImportError:
    print("This package requires 'setuptools' to be installed.")
    sys.exit(1)

requirements = ['rdflib', 'lxml', 'otsrdflib', 'iso-639']

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

setup(name='mc2skos',
      version='0.2.1',
      description='Convert Marc21 Classification records in MARC/XML to SKOS/RDF ',
      long_description=README,
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7'
      ],
      keywords='marc rdf skos',
      author='Dan Michael O. Heggø',
      author_email='danmichaelo@gmail.com',
      url='https://github.com/scriptotek/mc2skos',
      license='MIT',
      install_requires=requirements,
      test_suite='nose.collector',
      test_require=['nose','coverage'],
      packages=['mc2skos'],
      entry_points={'console_scripts': ['mc2skos=mc2skos.mc2skos:main']}
      )
