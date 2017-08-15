# -*- coding: utf-8 -*-
import unittest

from openregistry.api.utils import (
    generate_id
)


class UtilsTest(unittest.TestCase):

    def test_generate_id(self):
        id = generate_id()
        self.assertEqual(len(id), 32)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(UtilsTest))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
