from schematics.exceptions import ModelValidationError, ModelConversionError
from openregistry.api.utils import apply_data_patch, update_logging_context, error_handler, raise_operation_error


def validate_json_data(request):
    try:
        json = request.json_body
    except ValueError, e:
        request.errors.add('body', 'data', e.message)
        request.errors.status = 422
        raise error_handler(request)
    if not isinstance(json, dict) or 'data' not in json or not isinstance(json.get('data'), dict):
        request.errors.add('body', 'data', "Data not available")
        request.errors.status = 422
        raise error_handler(request)
    request.validated['json_data'] = json['data']
    return json['data']


def validate_data(request, model, partial=False, data=None):
    if data is None:
        data = validate_json_data(request)
    try:
        if partial and isinstance(request.context, model):
            initial_data = request.context.serialize()
            m = model(initial_data)
            new_patch = apply_data_patch(initial_data, data)
            if new_patch:
                m.import_data(new_patch, partial=True, strict=True)
            m.__parent__ = request.context.__parent__
            m.validate()
            role = request.context.get_role()
            method = m.to_patch
        else:
            m = model(data)
            m.__parent__ = request.context
            m.validate()
            method = m.serialize
            role = 'create'
    except (ModelValidationError, ModelConversionError), e:
        for i in e.message:
            request.errors.add('body', i, e.message[i])
        request.errors.status = 422
        raise error_handler(request)
    except ValueError, e:
        request.errors.add('body', 'data', e.message)
        request.errors.status = 422
        raise error_handler(request)
    else:
        if hasattr(type(m), '_options') and role not in type(m)._options.roles:
            request.errors.add('url', 'role', 'Forbidden')
            request.errors.status = 403
            raise error_handler(request)
        else:
            data = method(role)
            request.validated['data'] = data
            if not partial:
                m = model(data)
                m.__parent__ = request.context
                request.validated[model.__name__.lower()] = m
    return data


def validate_change_status(request, error_handler, **kwargs):
    """
        This validator get dict from adapter and validate availibility
        to change status by dict.
    """
    # Get resource_type
    resource_type = request.validated['resource_type']
    # Get status from PATCH validated data
    new_status = request.validated['data'].get("status")
    # Get model from context
    model = request.context

    # Check status in data and not equal to context status
    if not new_status or new_status == model.status:
        return

    # get available statuses from dict
    statuses = request.content_configurator.available_statuses[model.status]['next_status']
    # verify right status change (auth_role and target status)
    msg = 'Can\'t update {} in current ({}) status'.format(resource_type,
                                                           model.status)

    if new_status not in statuses or \
            request.authenticated_role not in statuses.get(new_status, {}):
        raise_operation_error(request, error_handler, msg)


# Document validators

def validate_patch_document_data(request, error_handler, **kwargs):
    model = type(request.context)
    return validate_data(request, model, True)


def validate_file_upload(request, error_handler, **kwargs):
    update_logging_context(request, {'document_id': '__new__'})
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        request.errors.add('body', 'file', 'Not Found')
        request.errors.status = 404
        raise error_handler(request)
    else:
        request.validated['file'] = request.POST['file']


def validate_file_update(request, error_handler, **kwargs):
    if request.content_type == 'multipart/form-data':
        validate_file_upload(request, error_handler, **kwargs)
