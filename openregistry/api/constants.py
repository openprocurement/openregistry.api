# -*- coding: utf-8 -*-
from pkg_resources import get_distribution
from logging import getLogger
import os
import re
from pytz import timezone
from requests import Session

SESSION = Session()

PKG = get_distribution(__package__)

LOGGER = getLogger(PKG.project_name)

TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')

DOCUMENT_BLACKLISTED_FIELDS = ('title', 'format', 'url', 'dateModified', 'hash')
DOCUMENT_WHITELISTED_FIELDS = ('id', 'datePublished', 'author', '__parent__')


def read_json(name):
    import os.path
    from json import loads
    curr_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(curr_dir, name)
    with open(file_path) as lang_file:
        data = lang_file.read()
    return loads(data)

DEFAULT_CURRENCY = u'UAH'

DEFAULT_ITEM_CLASSIFICATION = u'CAV'

DOCUMENT_TYPES = ['notice', 'technicalSpecifications', 'illustration', 'virtualDataRoom', 'x_presentation']

CPV_CODES = read_json('cpv.json')
CAV_CODES = read_json('cav.json')

ITEM_CLASSIFICATIONS = {
    u'CAV': CAV_CODES,
    #u'CAV': CAV_CODES,
    #u'CAV-PS': []
}

ORA_CODES = [i['code'] for i in read_json('OrganisationRegistrationAgency.json')['data']]

IDENTIFIER_CODES = ORA_CODES

ADDITIONAL_CLASSIFICATIONS_SCHEMES = [u'ДКПП', u'NONE', u'CPVS']

COORDINATES_REG_EXP = re.compile(r'-?\d{1,3}\.\d+|-?\d{1,3}')

VERSION = '{}.{}'.format(int(PKG.parsed_version[0]), int(PKG.parsed_version[1]) if PKG.parsed_version[1].isdigit() else 0)
ROUTE_PREFIX = '/api/{}'.format(VERSION)

SCHEMA_VERSION = 1
SCHEMA_DOC = 'openregistry_schema'