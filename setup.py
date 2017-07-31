import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()

requires = [
    'chaussette',
    'rfc6266',
    'cornice',
    'couchdb-schematics',
    'gevent',
    'iso8601',
    'jsonpatch',
    'libnacl',
    'pbkdf2',
    'pycrypto',
    'pyramid_exclog',
    'requests',
    'tzlocal',
]
test_requires = requires + [
    'webtest',
    'python-coveralls',
    'mock'
]

entry_points = {
    'paste.app_factory': [
        'main = openregistry.api.app:main'
    ],
    'openregistry.api.plugins': [
        'api = openregistry.api.includeme:includeme'
    ],
    'console_scripts': [
        'bootstrap_api_security = openregistry.api.database:bootstrap_api_security'
    ],
    'openregistry.tests': [
        'api_test_suite = openregistry.api.tests.main:suite'
    ]
}

setup(name='openregistry.api',
      version='0.1.dev1',
      description='openregistry.api',
      long_description=README,
      classifiers=[
          "Framework :: Pylons",
          "License :: OSI Approved :: Apache Software License",
          "Programming Language :: Python",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
      ],
      keywords="web services",
      author='Quintagroup, Ltd.',
      author_email='info@quintagroup.com',
      license='Apache License 2.0',
      url='https://github.com/openprocurement/openregistry.api',
      py_modules=['cgi'],
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['openregistry'],
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=test_requires,
      extras_require={'test': test_requires},
      test_suite="openregistry.api.tests.main.suite",
      entry_points=entry_points
)
