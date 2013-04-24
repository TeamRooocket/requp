__VERSION__ = '0.0.1'
import os
import sys
from setuptools import setup, find_packages, Command


install_requires = []
with open('requires.txt', 'r') as fh:
    install_requires = map(lambda s: s.strip(), filter(
        lambda l: not l.startswith('-e'), fh.readlines()))

tests_requires = []
with open('test-requires.txt', 'r') as fh:
    tests_requires = map(lambda s: s.strip(), filter(
        lambda l: not l.startswith('-e'), fh.readlines()))

readme = []
with open('README.md', 'r') as fh:
    readme = fh.readlines()

setup(
    name='requp',
    version=__VERSION__,
    author='German Ilyin',
    author_email='germanilyin@gmail.com',
    url='http://github.com/yunmanger1/requp',
    description='requires.txt updater',
    long_description=''.join(readme),
    packages=find_packages(exclude=['tests', 'tests.*']),
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_requires,
    extras_require={'test': tests_requires},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'requp = requp.runner:main'
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
    ],
)
