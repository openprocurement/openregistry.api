# -*- coding: utf-8 -*-

import unittest

from openregistry.api.tests import auth, spore, migration, models, utils
from openregistry.api.tests.dummy_resource import test


def suite():
    tests = unittest.TestSuite()
    tests.addTest(auth.suite())
    tests.addTest(spore.suite())
    tests.addTest(migration.suite())
    tests.addTest(models.suite())
    tests.addTest(utils.suite())
    tests.addTest(test.suite())
    return tests


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
