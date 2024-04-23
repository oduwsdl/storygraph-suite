#!/usr/bin/env python
#import os
from setuptools import setup, find_packages

desc = """A collection of software used by StoryGraphs (http://storygraph.cs.odu.edu/)"""

__appversion__ = None

#__appversion__, defined here
exec(open('sgsuite/version.py').read())

setup(
    name='sgsuite',
    version=__appversion__,
    description=desc,
    long_description='A collection of software used by StoryGraphs (http://storygraph.cs.odu.edu/) See documentation: https://github.com/oduwsdl/storygraph-suite',
    author='Alexander C. Nwala',
    author_email='alexandernwala@gmail.com',
    url='https://github.com/oduwsdl/storygraph-suite',
    packages=find_packages(),
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    install_requires=[
        'beautifulsoup4>=4.8',
        'boilerpy3',
        'dateparser>=0.7',
        'feedparser>=5.2',
        'requests>=2.20',
        'tldextract>=2.2',
        'networkx>=2.4',
        'NwalaTextUtils==0.0.4',
        'spacy>=3.1.0',
	'urllib3<2.0'
    ],
    scripts=[
        'bin/sgs'
    ]
)
