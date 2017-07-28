# -*- coding: utf-8 -*-

import unittest

from openregistry.api.tests import auth, spore, migration, models


def suite():
    suite = unittest.TestSuite()
    suite.addTest(auth.suite())
    suite.addTest(spore.suite())
    suite.addTest(migration.suite())
    suite.addTest(models.suite())
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
