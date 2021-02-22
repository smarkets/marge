import os
from distutils.core import setup
VERSION = open(os.path.join(os.path.dirname(__file__),  'version')).read().strip()
setup(
    name='marge',
    version=VERSION,
    license='BSD3',
    packages=['marge'],
    scripts=['marge.app'],
    data_files=[('.', ['version'])],
)
