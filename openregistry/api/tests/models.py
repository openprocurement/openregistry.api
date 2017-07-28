# -*- coding: utf-8 -*-
import unittest
import mock
from datetime import datetime, timedelta
from schematics.exceptions import ConversionError, DataError

from openregistry.api.utils import get_now

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

    @mock.patch.dict('openregistry.api.constants.ITEM_CLASSIFICATIONS', {'CPV': ('test', )})
    def test_ItemClassification_model(self):

        item_classification = ItemClassification.get_mock_object()
        self.assertNotIn('id', item_classification.serialize().keys())
        self.assertIn('id', item_classification.to_patch().keys())

        with self.assertRaises(DataError):
            item_classification.validate()  # {"id": ["Value must be one of ('test',)."]}
        self.assertNotIn('id', item_classification.to_patch().keys())
        with self.assertRaisesRegexp(KeyError, 'id'):
            item_classification.serialize()
            item_classification.validate()

        item_classification.id = 'test'
        item_classification.validate()


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DummyModelsTest))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
