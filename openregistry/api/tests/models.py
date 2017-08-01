# -*- coding: utf-8 -*-
import unittest
import mock
from datetime import datetime, timedelta
from schematics.exceptions import ConversionError, ValidationError, DataError

from openregistry.api.utils import get_now

from openregistry.api.models import blacklist
from openregistry.api.models import (
    Organization, ContactPoint, Identifier, Address,
    Item, Location, Unit, Value, ItemClassification, Classification,
    Period, PeriodEndRequired, IsoDateTimeType,
    Revision, Document, HashType
)


now = get_now()


class DummyModelsTest(unittest.TestCase):
    """ Test Case for testing openregistry.api.models'
            - roles
            - serialization
            - validation
    """

    def test_IsoDateTimeType_model(self):

        dt = IsoDateTimeType()

        value = dt.to_primitive(now)
        self.assertEqual(now, dt.to_native(now))
        self.assertEqual(now, dt.to_native(value))

        date = datetime.now()
        value = dt.to_primitive(date)
        self.assertEqual(date, dt.to_native(date))
        self.assertEqual(now.tzinfo, dt.to_native(value).tzinfo)

        # ParseError
        for date in (None, '', 2017, "2007-06-23X06:40:34.00Z"):
            with self.assertRaisesRegexp(ConversionError, 
                      u'Could not parse %s. Should be ISO8601.' % date):
                dt.to_native(date)
        # OverflowError
        for date in (datetime.max, datetime.min):
            self.assertEqual(date, dt.to_native(date))
            with self.assertRaises(ConversionError):
                dt.to_native(dt.to_primitive(date))

    def test_Period_model(self):

        period = Period()
        self.assertEqual(period.serialize(), {})

        period.startDate = now
        period.validate()
        self.assertEqual(period.serialize().keys(),
                         ['startDate'])
        period.endDate = now
        period.validate()
        self.assertEqual(period.serialize().keys(),
                         ['startDate', 'endDate'])
        period.startDate += timedelta(3)
        with self.assertRaises(DataError):
            period.validate()  # {"startDate": ["period should begin before its end"]}

    def test_PeriodEndRequired_model(self):

        period = PeriodEndRequired()
        self.assertEqual(period.serialize(), {})

        period.endDate = now
        period.validate()

        period.startDate = now + timedelta(1)
        with self.assertRaises(DataError):
            period.validate()  # {"startDate": ["period should begin before its end"]})

        period.endDate = None
        with self.assertRaises(DataError):
            period.validate()  # {'endDate': [u'This field is required.']}

        period.endDate = now + timedelta(2)
        period.validate()

    def test_Value_model(self):

        value = Value()
        self.assertEqual(value.serialize().keys(),
                         ['currency', 'valueAddedTaxIncluded'])
        self.assertEqual(Value.get_mock_object().serialize().keys(),
                         ['currency', 'amount', 'valueAddedTaxIncluded'])
        with self.assertRaises(DataError):
            value.validate()  # {'amount': [u'This field is required.']}

        value.amount = -10
        self.assertEqual(value.to_patch(), {'currency': u'UAH', 'amount': -10,
                                            'valueAddedTaxIncluded': True})
        self.assertEqual(value.serialize().keys(), ['currency', 'valueAddedTaxIncluded'])
        with self.assertRaises(DataError):
            value.validate()  # {'amount': [u'Float value should be greater than 0.']}
        self.assertTrue(value.to_patch() == value.serialize() == {'currency': u'UAH',
                                                                  'valueAddedTaxIncluded': True})
        with self.assertRaises(DataError):
            value.validate()  # {"amount": ["This field is required."]}

        value.amount = .0
        value.currency = None
        self.assertEqual(value.serialize(),
                         {'currency': u'UAH', 'amount': 0.0, 'valueAddedTaxIncluded': True})
        with self.assertRaises(DataError):
            value.validate()  # {"currency": ["This field is required."]}
        self.assertEqual(value.amount, 0)
        self.assertEqual(value.currency, u'UAH')

    def test_Unit_model(self):

        data = {'name': u'item', 'code': u'44617100-9'}

        unit = Unit(data)
        unit.validate()
        self.assertEqual(unit.serialize().keys(), ['code', 'name'])

        unit.code = None
        with self.assertRaises(DataError):
            unit.validate()  # {'code': [u'This field is required.']}

        data['value'] = {'amount': 5}
        unit = Unit(data)
        self.assertEqual(unit.serialize(), {'code': u'44617100-9', 'name': u'item',
                         'value': {'currency': u'UAH', 'amount': 5., 'valueAddedTaxIncluded': True}})

        unit.value.amount = -1000
        unit.value.valueAddedTaxIncluded = False
        with self.assertRaises(DataError):
            unit.validate()  # {'value': {'amount': [u'Float value should be greater than 0.']}}
        self.assertEqual(unit.serialize(), {'code': u'44617100-9', 'name': u'item',
                         'value': {'currency': u'UAH', 'valueAddedTaxIncluded': False}})

    def test_Classification_model(self):

        data = {'scheme': u'CPV', 'id': u'44617100-9', 'description': u'Cartons'}

        classification = Classification(data)
        classification.validate()
        self.assertEqual(classification.serialize(), data)

        classification.scheme = None
        self.assertEqual(classification.to_patch().keys(), ['id', 'description'])
        self.assertNotEqual(classification.to_patch(), classification.serialize())
        with self.assertRaises(DataError):
            classification.validate()  # {"scheme": ["This field is required."]}

        self.assertTrue(classification.serialize() == classification.to_patch() == data)
        classification.validate()

    @mock.patch.dict('openregistry.api.constants.ITEM_CLASSIFICATIONS', {'CPV': ('test', ),
                                                                         'CAV-PS': ('test2')})
    def test_ItemClassification_model(self):

        item_classification = ItemClassification.get_mock_object()
        self.assertNotIn('id', item_classification.serialize().keys())
        self.assertIn('id', item_classification.to_patch().keys())

        with self.assertRaises(DataError):
            item_classification.validate()  # {"id": ["Value must be one of ('test',)."]}
        self.assertNotIn('id', item_classification.to_patch().keys())

        item_classification.import_data({'scheme': 'CPV', 'id': 'test'})
        item_classification.validate()

        item_classification.import_data({'scheme': 'CAV-PS', 'id': 'test2'})
        item_classification.validate()

    def test_Location_model(self):

        location = Location()
        self.assertEqual(location.serialize(), {})
        with self.assertRaises(DataError) as ex:
            location.validate()
        self.assertEqual(ex.exception, {'latitude': [u'This field is required.'],
                                        'longitude': [u'This field is required.']})
        location.import_data({'latitude': '123.1234567890',
                              'longitude': '-123.1234567890'})
        self.assertDictEqual(location.serialize(), {'latitude': '123.1234567890',
                                                    'longitude': '-123.1234567890'})
        location.validate()

    def test_Item_model(self):

        data = {
            "id": u"0",
            "description": u"футляри до державних нагород",
            "classification": {
                "scheme": u"CPV",
                "id": u"44617100-9",
                "description": u"Cartons"
            },
            "additionalClassifications": [
                {
                    "scheme": u"ДКПП",
                    "id": u"17.21.1",
                    "description": u"папір і картон гофровані, паперова й картонна тара"
                }
            ],
            "unit": {
                "name": u"item",
                "code": u"44617100-9"
            },
            "quantity": 5,
            "address": {
                "countryName": u"Україна",
                "postalCode": "79000",
                "region": u"м. Київ",
                "locality": u"м. Київ",
                "streetAddress": u"вул. Банкова 1"
            }
        }
        item = Item(data)
        item.validate()
        self.assertTrue(item.serialize() == item.to_patch() == data)

        data['location'] = {'latitude': '123', 'longitude': '567'}
        item2 = Item(data)
        item2.validate()
        self.assertTrue(item2.serialize() == item2.to_patch() == data)

        self.assertNotEqual(item, item2)
        item2.location = None
        self.assertEqual(item, item2)

        with mock.patch.dict('openregistry.api.models.Item._options.roles', {'test': blacklist('__parent__', 'address')}):
            self.assertNotIn('address', item.serialize('test'))
            self.assertNotEqual(item.serialize('test'), item.serialize())
            self.assertEqual(item.serialize('test'), item2.serialize('test'))

    def test_Address_model(self):

        data = {
            "countryName": u"Україна",
            "postalCode": "79000",
            "region": u"м. Київ",
            "locality": u"м. Київ",
            "streetAddress": u"вул. Банкова 1"
        }

        address = Address(data)
        address.validate()
        self.assertEqual(address.serialize(), data)

        address.countryName = None
        with self.assertRaises(DataError) as ex:
            address.validate()
        self.assertEqual(ex.exception, {"countryName": ["This field is required."]})
        self.assertEqual(address.serialize(), data)

    def test_Identifier_model(self):

        identifier = Identifier.get_mock_object()
        with self.assertRaises(DataError) as ex:
            identifier.validate()
        self.assertEqual(ex.exception, {"id": ["This field is required."]})

        identifier.id = 'test'
        identifier.validate()

        with mock.patch.dict('openregistry.api.models.Identifier._options.roles', {'test': blacklist('id')}):
            self.assertIn('id', identifier.serialize().keys())
            self.assertNotIn('id', identifier.serialize('test').keys())

    def test_ContactPoint_model(self):

        contact = ContactPoint()
        self.assertEqual(contact.serialize(), {})

        with self.assertRaises(DataError) as ex:
            contact.validate()
        self.assertEqual(ex.exception, {"name": ["This field is required."],
                                        "email": ["telephone or email should be present"]})
        data = {"name": u"Державне управління справами",
                "telephone": u"0440000000"}
        contact.import_data(data)
        contact.validate()
        self.assertEqual(contact.serialize(), data)

        contact.telephone = None
        with self.assertRaisesRegexp(KeyError, 'email'):
            contact.validate()
        self.assertEqual(contact.serialize(), data)

        data['email'] = 'qwe@example.test'
        contact.email = data['email']
        contact.validate()
        self.assertEqual(contact.serialize(), data)

        contact.telephone = None
        contact.validate()
        self.assertNotEqual(contact.serialize(), data)
        data.pop('telephone')
        self.assertEqual(contact.serialize(), data)

    def test_Organization_model(self):

        data = {
            "name": u"Державне управління справами",
            "identifier": {
                "scheme": u"UA-EDR",
                "id": u"00037256",
                "uri": u"http://www.dus.gov.ua/"
            },
            "address": {
                "countryName": u"Україна",
                "postalCode": u"01220",
                "region": u"м. Київ",
                "locality": u"м. Київ",
                "streetAddress": u"вул. Банкова, 11, корпус 1"
            },
            "contactPoint": {
                "name": u"Державне управління справами",
                "telephone": u"0440000000"
            }
        }
        organization = Organization(data)
        organization.validate()
        self.assertEqual(organization.serialize(), data)

        with mock.patch.dict('openregistry.api.models.Identifier._options.roles', {'view': blacklist('id')}):
            self.assertNotEqual(organization.serialize('view'),
                                organization.serialize())
            self.assertIn('id', organization.serialize()['identifier'].keys())
            self.assertNotIn('id', organization.serialize('view')['identifier'].keys())

        additional_identifiers = []
        for _ in xrange(3):
            idtf = Identifier.get_mock_object()
            idtf.id = '0' * 6
            additional_identifiers.append(idtf.serialize())
        data['additionalIdentifiers'] = additional_identifiers

        organization2 = Organization(data)
        organization2.validate()
        self.assertNotEqual(organization, organization2)
        self.assertEqual(organization2.serialize(), data)

    def test_HashType_model(self):
        from uuid import uuid4

        hash = HashType()

        for invalid_hash in ['test', ':', 'test:']:
            with self.assertRaisesRegexp(ValidationError, "Hash type is not supported."):
                hash.to_native(invalid_hash)

        with self.assertRaisesRegexp(ValidationError, "Hash value is wrong length."):
            hash.to_native('sha512:')

        with self.assertRaisesRegexp(ConversionError, "Hash value is not hexadecimal."):
            hash.to_native('md5:{}'.format('-' * 32))

        result = 'md5:{}'.format(uuid4().hex)
        self.assertEqual(hash.to_native(result), result)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DummyModelsTest))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
