# -*- coding: utf-8 -*-
from cornice.service import Service, get_services
from openregistry.api.constants import VERSION
from cornice_swagger.swagger import CorniceSwagger


swagger = Service(name='swagger_docs', path='/swagger', renderer='json')

@swagger.get()
def get_swagger(request):
    swagger_generator = CorniceSwagger(get_services())
    return swagger_generator(
        'Open Registry API',
        request.registry.settings.get(
            'api_version',
            VERSION
        )
    )

