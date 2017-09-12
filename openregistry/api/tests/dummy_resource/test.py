# -*- coding: utf-8 -*-
import os
import unittest
from pyramid import testing
from mock import Mock, MagicMock, patch

from urllib import unquote
from base64 import b64decode
from paste.deploy.loadwsgi import appconfig
from schematics.transforms import wholelist
from schematics.types.compound import ModelType

from openregistry.api.models.ocds import Document
from openregistry.api.models.schematics_extender import ListType

from openregistry.api.tests.dummy_resource.views import DummyResource
from openregistry.api.tests.dummy_resource.models import DummyModel


settings = appconfig('config:' + os.path.join(os.path.dirname(__file__), '..', 'tests.ini'))


class BaseAPIUnitTest(unittest.TestCase):
    """ Base TestCase class for unit tests of API functionality
    """

    def setUp(self):
        self.config = testing.setUp()
        self.request = testing.DummyRequest()

    def tearDown(self):
        testing.tearDown()


class TestAPIResourceListing(BaseAPIUnitTest):
    """ TestCase for APIResource and APIResourceListing
    """

    def setUp(self):
        super(TestAPIResourceListing, self).setUp()
        self.config.include('cornice')
        self.config.scan('.views')

        self.request.registry.db = Mock()
        self.request.registry.server_id = Mock()
        self.request.registry.couchdb_server = Mock()
        self.request.registry.update_after = True

        self.context = Mock()

    def test_01_listing(self):

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])
        self.assertNotIn('prev_page', response)

    def test_02_listing_opt_fields(self):

        self.request.params['opt_fields'] = 'status'
        self.request.logging_context = MagicMock()

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])

    def test_03_listing_limit(self):

        self.request.params['limit'] = '10'

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])

    def test_04_listing_offset(self):

        self.request.params['offset'] = '2015-01-01T00:00:00+02:00'

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])

    def test_05_listing_descending(self):

        self.request.params['descending'] = '1'

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])

    def test_06_listing_feed(self):

        self.request.params['feed'] = 'changes'

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])

    def test_07_listing_mode(self):

        self.request.params['mode'] = u'test'

        view = DummyResource(self.request, self.context)
        response = view.get()

        self.assertEqual(response['data'], [])

    def test_08_listing_feed_and_offset_error(self):

        self.request.errors = Mock(**{'add': Mock()})

        self.request.params['feed'] = 'changes'
        self.request.params['offset'] = '0'

        view = DummyResource(self.request, self.context)

        class OffsetExpired(Exception):
            """ Test exception for error_handler mocking"""

        with patch('openregistry.api.utils.error_handler',
                   return_value=OffsetExpired):
            with self.assertRaises(OffsetExpired):
                view.get()


class TestAPIValidation(BaseAPIUnitTest):
    """ TestCase for API validators
    """

    def setUp(self):
        super(TestAPIValidation, self).setUp()

        self.request.validated = {}
        self.request.errors = Mock(**{'add': Mock()})

    def test_01_json_data(self):
        from openregistry.api.validation import validate_json_data

        class DataNotAvailable(Exception):
            """ Test exception for error_handler mocking """

        with patch('openregistry.api.validation.error_handler',
                   return_value=DataNotAvailable):
            with self.assertRaises(DataNotAvailable):
                self.request.json_body = {'data': None}
                result = validate_json_data(self.request)
                self.assertEqual(self.request.errors.status, 422)
                self.request.errors.add.assert_called_with(
                    'body', 'data', 'Data not available')

        self.request.json_body = {'data': {}}
        result = validate_json_data(self.request)
        self.assertEqual(result, {})
        self.assertEqual(self.request.validated['json_data'], {})

    def test_02_data(self):
        from openregistry.api.validation import validate_data

        model = DummyModel()
        self.request.context = model

        class ValidationError(Exception):
            """ Test exception for error_handler mocking """

        with patch('openregistry.api.validation.error_handler',
                   return_value=ValidationError):
            with self.assertRaises(ValidationError):
                result = validate_data(self.request, DummyModel, data={})
            self.assertEqual(self.request.errors.status, 403)
            self.request.errors.add.assert_called_once_with(
                'url', 'role', 'Forbidden')

            with self.assertRaises(ValidationError):
                result = validate_data(self.request, DummyModel, data={'mode': 'dev'})
            self.assertEqual(self.request.errors.status, 422)
            self.request.errors.add.assert_called_with(
                'body', 'mode', [u"Value must be one of ['test']."])

        DummyModel._options.roles['create'] = wholelist()
        self.request.json_body = {'data': {}}
        result = validate_data(self.request, DummyModel)
        self.assertEqual(result, {'doc_type': u'DummyModel', 'id': None, '__parent__': model})

        DummyModel._options.roles['edit'] = wholelist()
        self.request.context = Mock(**{
            'serialize.return_value': {},
            'get_role.return_value': 'edit',
            '__parent__': None,
            'spec': DummyModel
        })
        result = validate_data(self.request, DummyModel, partial=True, data={'mode': 'test'})
        self.assertEqual(result['mode'], u'test')

    def test_03_change_status(self):
        from openregistry.api.validation import validate_change_status

        self.request.validated.update({
            'resource_type': 'dummy_resource',
            'data': {}
        })
        self.request.context = Mock(**{'status': 'draft'})
        validate_change_status(self.request, Mock())

        self.request.validated['data']['status'] = 'pending'
        self.request.authenticated_role = 'test_owner'
        self.request.content_configurator = Mock(**{
            'available_statuses': {
                'draft': {
                    'editing_permissions': ['test_owner'],
                    'next_status': {}
                }
            }
        })

        class ForbiddenStatusChange(Exception):
            """ Test exception for error_handler mocking """

        with self.assertRaises(ForbiddenStatusChange):
            validate_change_status(self.request, Mock(return_value=ForbiddenStatusChange))
        self.assertEqual(self.request.errors.status, 403)
        self.request.errors.add.assert_called_once_with(
            'body', 'data', 'Can\'t update dummy_resource in current (draft) status')

        self.request.content_configurator.available_statuses['draft']['next_status'] = {'pending': 'test_owner'}
        validate_change_status(self.request, Mock())

    def test_04_check_document(self):
        from openregistry.api.utils import check_document

        self.request.registry.docservice_url = 'http://localhost/get'
        document = Document({
            'title': u'укр.doc',
            'url': 'http://localhost/get',
            'format': 'application/msword'
        })

        class InvalidDocument(Exception):
            """ Test exception for error_handler mocking """

        with patch('openregistry.api.utils.error_handler',
                   return_value=InvalidDocument):
            with self.assertRaises(InvalidDocument):
                check_document(self.request, document, 'body')
            self.assertEqual(self.request.errors.status, 403)
            self.request.errors.add.assert_called_once_with(
                'body', 'url', 'Can add document only from document service.')

            document.url = 'http://localhost/get/ee9cabd7e0384c9c8006563d4876b462?KeyID=c7925f5a&Signature=testing'
            with self.assertRaises(InvalidDocument):
                check_document(self.request, document, 'body')
            self.assertEqual(self.request.errors.status, 422)
            self.request.errors.add.assert_called_with(
                'body', 'hash', 'This field is required.')

            document.hash = 'md5:' + '0' * 32
            self.request.registry.keyring = {}
            with self.assertRaises(InvalidDocument):
                check_document(self.request, document, 'body')
            self.assertEqual(self.request.errors.status, 422)
            self.request.errors.add.assert_called_with(
                'body', 'url', 'Document url expired.')

            self.request.registry.keyring['c7925f5a'] = Mock(**{'verify.return_value': 'Test'})
            with self.assertRaises(InvalidDocument):
                check_document(self.request, document, 'body')
            self.assertEqual(self.request.errors.status, 422)
            self.request.errors.add.assert_called_with(
                'body', 'url', 'Document url signature invalid.')

            document.url = 'http://localhost/get/ee9cabd7e0384c9c8006563d4876b462?KeyID=c7925f5a&Signature=NsjG53XRPUq%2F4rHU79t3JLW6FTLPH8KjLIqKxjIaH6oBMbKIQSwtzAL1T%2F%2BbpA7lLErHpOxq3a1KJx9HI9azDg%3D%3D'
            signature = b64decode(unquote('NsjG53XRPUq%2F4rHU79t3JLW6FTLPH8KjLIqKxjIaH6oBMbKIQSwtzAL1T%2F%2BbpA7lLErHpOxq3a1KJx9HI9azDg%3D%3D'))
            with self.assertRaises(InvalidDocument):
                check_document(self.request, document, 'body')
            self.assertEqual(self.request.errors.status, 422)
            self.request.errors.add.assert_called_with(
                'body', 'url', 'Document url invalid.')
            verification_message = 'ee9cabd7e0384c9c8006563d4876b462\0' + '0' * 32
            self.request.registry.keyring['c7925f5a'].verify.assert_called_once_with(
                signature + verification_message.encode('utf-8'))

        self.request.registry.keyring['c7925f5a'].verify.return_value = verification_message
        check_document(self.request, document, 'body')

    def test_05_document_data(self):
        from openregistry.api.validation import validate_document_data

        class TestModel(DummyModel):
            documents = ListType(ModelType(Document), default=list())

        self.request.context = TestModel()
        self.request.matched_route = Mock(**{
            'name.replace.return_value': 'test:DummyResource Documents'})
        self.request.current_route_path = Mock(
            return_value='/api/0.1/dummy_resources/b98c61fd4bde4001babef81cc6aad23d/documents/6fa5d3a2bdb049f4a13e8b5d8af7bbfd?download=ee9cabd7e0384c9c8006563d4876b462')
        self.request.json_body = {
            'data': {
                'title': u'укр.doc',
                'url': 'http://localhost/get',
                'hash': 'md5:' + '0' * 32,
                'format': 'application/msword'
            }
        }
        with patch('openregistry.api.validation.check_document',
                   return_value=None):
            validate_document_data(self.request, Mock())
        self.assertEqual(self.request.validated['document'].documentOf, 'testmodel')
        self.assertEqual(self.request.validated['document'].url,
                         '/dummy_resources/b98c61fd4bde4001babef81cc6aad23d/documents/6fa5d3a2bdb049f4a13e8b5d8af7bbfd?download=ee9cabd7e0384c9c8006563d4876b462')


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(TestAPIResourceListing))
    tests.addTest(unittest.makeSuite(TestAPIValidation))
    return tests


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
