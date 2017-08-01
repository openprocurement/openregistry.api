# -*- coding: utf-8 -*-
from datetime import datetime
from iso8601 import parse_date, ParseError
from hashlib import algorithms, new as hash_new
from urlparse import urlparse, parse_qs
from uuid import uuid4

from schematics.types import (StringType, FloatType, URLType, IntType,
                              BooleanType, BaseType, EmailType, MD5Type)
from schematics.transforms import whitelist, blacklist, export_loop, convert
from schematics.exceptions import ConversionError, ValidationError
from schematics.types.compound import ModelType, DictType, ListType
from schematics.models import Model as SchematicsModel
from schematics.types.serializable import serializable


from couchdb_schematics.document import SchematicsDocument

from openregistry.api.constants import ( DEFAULT_CURRENCY,
    DEFAULT_ITEM_CLASSIFICATION, ITEM_CLASSIFICATIONS, TZ, DOCUMENT_TYPES,
    IDENTIFIER_CODES
)
from openregistry.api.utils import get_now, set_parent

schematics_default_role = SchematicsDocument.Options.roles['default'] + blacklist("__parent__")
schematics_embedded_role = SchematicsDocument.Options.roles['embedded'] + blacklist("__parent__")

plain_role = (blacklist('_attachments', 'revisions', 'dateModified') + schematics_embedded_role)
listing_role = whitelist('dateModified', 'doc_id')
draft_role = whitelist('status')


class IsoDateTimeType(BaseType):
    MESSAGES = {
        'parse': u'Could not parse {0}. Should be ISO8601.',
    }

    def to_native(self, value, context=None):
        if isinstance(value, datetime):
            return value
        try:
            date = parse_date(value, None)
            if not date.tzinfo:
                date = TZ.localize(date)
            return date
        except ParseError:
            raise ConversionError(self.messages['parse'].format(value))
        except OverflowError as e:
            raise ConversionError(e.message)

    def to_primitive(self, value, context=None):
        return value.isoformat()


class Model(SchematicsModel):

    class Options(object):
        """Export options for Document."""
        serialize_when_none = False
        roles = {
            "default": blacklist("__parent__"),
            "embedded": blacklist("__parent__"),
        }

    __parent__ = BaseType()

    def __init__(self,*args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        for i, j in self._data.items():
            if isinstance(j, list):
                for x in j:
                    set_parent(x, self)
            else:
                set_parent(j, self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            for k in self._fields:
                if k != '__parent__' and self.get(k) != other.get(k):
                    return False
            return True
        return NotImplemented

    def serialize(self, *args, **kwargs):
        return super(Model, self).serialize(raise_error_on_role=False, *args, **kwargs)

    def to_patch(self, role=None, *arg, **kwargs):
        """
        Return data as it would be validated. No filtering of output unless
        role is defined.
        """
        field_converter = lambda field, value, context: field.to_primitive(value, context)
        data = export_loop(self.__class__, self, field_converter=field_converter, role=role, raise_error_on_role=False, *arg, **kwargs)
        return data

    def get_role(self):
        root = self.__parent__
        while root.__parent__ is not None:
            root = root.__parent__
        request = root.request
        return 'Administrator' if request.authenticated_role == 'Administrator' else 'edit'


class Value(Model):
    amount = FloatType(required=True, min_value=0)  # Amount as a number.
    currency = StringType(required=True, default=DEFAULT_CURRENCY, max_length=3, min_length=3)  # The currency in 3-letter ISO 4217 format.
    valueAddedTaxIncluded = BooleanType(required=True, default=True)


class Period(Model):
    startDate = IsoDateTimeType()  # The state date for the period.
    endDate = IsoDateTimeType()  # The end date for the period.

    def validate_startDate(self, data, value):
        if value and data.get('endDate') and data.get('endDate') < value:
            raise ValidationError(u"period should begin before its end")


class PeriodEndRequired(Period):
    endDate = IsoDateTimeType(required=True)  # The end date for the period.


class Classification(Model):
    scheme = StringType(required=True)  # The classification scheme for the goods
    id = StringType(required=True)  # The classification ID from the Scheme used
    description = StringType(required=True)  # A description of the goods, services to be provided.
    description_en = StringType()
    description_ru = StringType()
    uri = URLType()


class ItemClassification(Classification):
    scheme = StringType(required=True, default=DEFAULT_ITEM_CLASSIFICATION, choices=ITEM_CLASSIFICATIONS.keys())
    id = StringType(required=True)

    def validate_id(self, data, code):
        available_codes = ITEM_CLASSIFICATIONS.get(data.get('scheme'), [])
        if code not in available_codes:
            raise ValidationError(BaseType.MESSAGES['choices'].format(unicode(available_codes)))


class Unit(Model):
    """
    Description of the unit which the good comes in e.g. hours, kilograms.
    Made up of a unit name, and the value of a single unit.
    """

    name = StringType()
    name_en = StringType()
    name_ru = StringType()
    value = ModelType(Value)
    code = StringType(required=True)


class Address(Model):

    streetAddress = StringType()
    locality = StringType()
    region = StringType()
    postalCode = StringType()
    countryName = StringType(required=True)
    countryName_en = StringType()
    countryName_ru = StringType()


class Location(Model):
    latitude = BaseType(required=True)
    longitude = BaseType(required=True)
    elevation = BaseType()


class HashType(StringType):

    MESSAGES = {
        'hash_invalid': "Hash type is not supported.",
        'hash_length': "Hash value is wrong length.",
        'hash_hex': "Hash value is not hexadecimal.",
    }

    def to_native(self, value, context=None):
        value = super(HashType, self).to_native(value, context)

        if ':' not in value:
            raise ValidationError(self.messages['hash_invalid'])

        hash_type, hash_value = value.split(':', 1)

        if hash_type not in algorithms:
            raise ValidationError(self.messages['hash_invalid'])

        if len(hash_value) != hash_new(hash_type).digest_size * 2:
            raise ValidationError(self.messages['hash_length'])
        try:
            int(hash_value, 16)
        except ValueError:
            raise ConversionError(self.messages['hash_hex'])
        return value


class Document(Model):
    class Options:
        roles = {
            'create': blacklist('id', 'datePublished', 'dateModified', 'author', 'download_url'),
            'edit': blacklist('id', 'url', 'datePublished', 'dateModified', 'author', 'hash', 'download_url'),
            'embedded': (blacklist('url', 'download_url') + schematics_embedded_role),
            'default': blacklist("__parent__"),
            'view': (blacklist('revisions') + schematics_default_role),
            'revisions': whitelist('url', 'dateModified'),
        }

    id = MD5Type(required=True, default=lambda: uuid4().hex)
    hash = HashType()
    documentType = StringType(choices=DOCUMENT_TYPES)
    title = StringType(required=True)  # A title of the document.
    title_en = StringType()
    title_ru = StringType()
    description = StringType()  # A description of the document.
    description_en = StringType()
    description_ru = StringType()
    format = StringType(required=True, regex='^[-\w]+/[-\.\w\+]+$')
    url = StringType(required=True)  # Link to the document or attachment.
    datePublished = IsoDateTimeType(default=get_now)
    dateModified = IsoDateTimeType(default=get_now)  # Date that the document was last dateModified
    language = StringType()
    relatedItem = MD5Type()
    author = StringType()

    @serializable(serialized_name="url")
    def download_url(self):
        url = self.url
        if not url or '?download=' not in url:
            return url
        doc_id = parse_qs(urlparse(url).query)['download'][-1]
        root = self.__parent__
        parents = []
        while root.__parent__ is not None:
            parents[0:0] = [root]
            root = root.__parent__
        request = root.request
        if not request.registry.docservice_url:
            return url
        if 'status' in parents[0] and parents[0].status in type(parents[0])._options.roles:
            role = parents[0].status
            for index, obj in enumerate(parents):
                if obj.id != url.split('/')[(index - len(parents)) * 2 - 1]:
                    break
                field = url.split('/')[(index - len(parents)) * 2]
                if "_" in field:
                    field = field[0] + field.title().replace("_", "")[1:]
                roles = type(obj)._options.roles
                if roles[role if role in roles else 'default'](field, []):
                    return url
        from openregistry.api.utils import generate_docservice_url
        if not self.hash:
            path = [i for i in urlparse(url).path.split('/') if len(i) == 32 and not set(i).difference(hexdigits)]
            return generate_docservice_url(request, doc_id, False, '{}/{}'.format(path[0], path[-1]))
        return generate_docservice_url(request, doc_id, False)


class Identifier(Model):
    scheme = StringType(required=True, choices=IDENTIFIER_CODES)  # The scheme that holds the unique identifiers used to identify the item being identified.
    id = BaseType(required=True)  # The identifier of the organization in the selected scheme.
    legalName = StringType()  # The legally registered name of the organization.
    legalName_en = StringType()
    legalName_ru = StringType()
    uri = URLType()  # A URI to identify the organization.


class Item(Model):
    """A good, service, or work to be contracted."""
    id = StringType(required=True, min_length=1, default=lambda: uuid4().hex)
    description = StringType(required=True)  # A description of the goods, services to be provided.
    description_en = StringType()
    description_ru = StringType()
    classification = ModelType(ItemClassification)
    additionalClassifications = ListType(ModelType(Classification), default=list())
    unit = ModelType(Unit)  # Description of the unit which the good comes in e.g. hours, kilograms
    quantity = IntType()  # The number of units required
    address = ModelType(Address)
    location = ModelType(Location)
    relatedLot = MD5Type()


class ContactPoint(Model):
    name = StringType(required=True)
    name_en = StringType()
    name_ru = StringType()
    email = EmailType()
    telephone = StringType()
    faxNumber = StringType()
    url = URLType()

    def validate_email(self, data, value):
        if not value and not data.get('telephone'):
            raise ValidationError(u"telephone or email should be present")


class Organization(Model):
    """An organization."""
    class Options:
        roles = {
            'embedded': schematics_embedded_role,
            'view': schematics_default_role,
        }

    name = StringType(required=True)
    name_en = StringType()
    name_ru = StringType()
    identifier = ModelType(Identifier, required=True)
    additionalIdentifiers = ListType(ModelType(Identifier))
    address = ModelType(Address, required=True)
    contactPoint = ModelType(ContactPoint, required=True)


class Revision(Model):
    author = StringType()
    date = IsoDateTimeType(default=get_now)
    changes = ListType(DictType(BaseType), default=list())
    rev = StringType()