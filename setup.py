#!/usr/bin/env python

from setuptools import setup, find_packages

desc = """A collection of software used by StoryGraphs (http://storygraph.cs.odu.edu/)"""

__appversion__ = None

#__appversion__, defined here
exec(open('sgsuite/config.py').read())

setup(
    name='sgsuite',
    version=__appversion__,
    description=desc,
    long_description='A collection of software used by StoryGraphs (http://storygraph.cs.odu.edu/)',
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
    package_data={
        'sgsuite': [
            './sample_txt/*'
        ]
    },
    install_requires=[
        'beautifulsoup4>=4.8',
        'boilerpy3',
        'feedparser>=5.2',
        'requests>=2.20',
        'tldextract>=2.2',
        'networkx>=2.4'
    ]
)