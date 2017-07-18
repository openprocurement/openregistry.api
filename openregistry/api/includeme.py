# -*- coding: utf-8 -*-
from pyramid.interfaces import IRequest
from openregistry.api.interfaces import IContentConfigurator, IORContent
from openregistry.api.adapters import ContentConfigurator
from openregistry.api.utils import get_content_configurator


def includeme(config):
    config.scan("openregistry.api.views")
    config.scan("openregistry.api.subscribers")
    config.registry.registerAdapter(ContentConfigurator, (IORContent, IRequest),
                                    IContentConfigurator)
    config.add_request_method(get_content_configurator, 'content_configurator', reify=True)
