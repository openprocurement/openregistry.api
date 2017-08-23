# -*- coding: utf-8 -*-

from openregistry.api.tests.base import snitch

from .core_resource import empty_listing
from .resource import (
    listing,
    listing_changes,
    listing_draft,
    resource_not_found,
    dateModified_resource,
    get_resource,
    create_resource
)


class CoreResourceTestMixin(object):
    """ Mixin that contains tests for core packages
    """

    test_empty_listing = snitch(empty_listing)


class ResourceTestMixin(object):
    """ Mixin with common tests for Asset and Lot
    """

    test_01_listing = snitch(listing)
    test_02_listing_changes = snitch(listing_changes)
    test_03_listing_draft = snitch(listing_draft)
    test_04_resource_not_found = snitch(resource_not_found)
    test_05_dateModified_resource = snitch(dateModified_resource)
    test_06_get_resource = snitch(get_resource)
    test_07_create_resource = snitch(create_resource)
