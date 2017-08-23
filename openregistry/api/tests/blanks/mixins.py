# -*- coding: utf-8 -*-

from openregistry.api.tests.base import snitch

from .core_resource import empty_listing


class CoreResourceTestMixin(object):
    """ Mixin that contains tests for core packages
    """

    test_empty_listing = snitch(empty_listing)
