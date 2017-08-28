# -*- coding: utf-8 -*-
import unittest
from pyramid import testing
from openregistry.api.auth import AuthenticationPolicy
from pyramid.tests.test_authentication import TestBasicAuthAuthenticationPolicy
import os


dir_path = os.path.dirname(os.path.realpath(__file__))


class AuthTest(TestBasicAuthAuthenticationPolicy):
    def _makeOne(self, check):
        return AuthenticationPolicy(os.path.join(dir_path, 'auth.ini'), 'SomeRealm')

    test_authenticated_userid_utf8 = None
    test_authenticated_userid_latin1 = None

    def test_unauthenticated_userid_bearer(self):
        request = testing.DummyRequest()
        request.headers['Authorization'] = 'Bearer chrisr'
        policy = self._makeOne(None)
        self.assertEqual(policy.unauthenticated_userid(request), 'chrisr')


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(AuthTest))
    return tests


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
