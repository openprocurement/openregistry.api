# -*- coding: utf-8 -*-
from datetime import datetime
from string import hexdigits
from json import dumps
from uuid import uuid4
from functools import partial
from logging import getLogger
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from cornice.util import json_error
from cornice.resource import view
from webob.multidict import NestedMultiDict
from pkg_resources import iter_entry_points
from urlparse import urlparse, parse_qs
from urllib import quote
from base64 import b64encode
from hashlib import sha512
from email.header import decode_header
from rfc6266 import build_header

from schematics.types import StringType
from jsonpatch import make_patch, apply_patch as _apply_patch

from openregistry.api.events import ErrorDesctiptorEvent
from openregistry.api.constants import (
    LOGGER, TZ, ROUTE_PREFIX,
    DOCUMENT_BLACKLISTED_FIELDS, DOCUMENT_WHITELISTED_FIELDS
)
from openregistry.api.interfaces import IContentConfigurator


json_view = partial(view, renderer='json')


def load_plugins(config, group, **kwargs):
    plugins = kwargs.get('plugins')
    for entry_point in iter_entry_points(group, kwargs.get('name')):
        if not plugins or entry_point.name in plugins:
            plugin = entry_point.load()
            plugin(config)


def get_now():
    return datetime.now(TZ)


def set_parent(item, parent):
    if hasattr(item, '__parent__') and item.__parent__ is None:
        item.__parent__ = parent


def encrypt(uuid, name, key):
    iv = "{:^{}.{}}".format(name, AES.block_size, AES.block_size)
    text = "{:^{}}".format(key, AES.block_size)
    return hexlify(AES.new(uuid, AES.MODE_CBC, iv).encrypt(text))


def decrypt(uuid, name, key):
    iv = "{:^{}.{}}".format(name, AES.block_size, AES.block_size)
    try:
        text = AES.new(uuid, AES.MODE_CBC, iv).decrypt(unhexlify(key)).strip()
    except:
        text = ''
    return text


def generate_id():
    return uuid4().hex


def prepare_patch(changes, orig, patch, basepath=''):
    if isinstance(patch, dict):
        for i in patch:
            if i in orig:
                prepare_patch(changes, orig[i], patch[i], '{}/{}'.format(basepath, i))
            else:
                changes.append({'op': 'add', 'path': '{}/{}'.format(basepath, i), 'value': patch[i]})
    elif isinstance(patch, list):
        if len(patch) < len(orig):
            for i in reversed(range(len(patch), len(orig))):
                changes.append({'op': 'remove', 'path': '{}/{}'.format(basepath, i)})
        for i, j in enumerate(patch):
            if len(orig) > i:
                prepare_patch(changes, orig[i], patch[i], '{}/{}'.format(basepath, i))
            else:
                changes.append({'op': 'add', 'path': '{}/{}'.format(basepath, i), 'value': j})
    else:
        for x in make_patch(orig, patch).patch:
            x['path'] = '{}{}'.format(basepath, x['path'])
            changes.append(x)


def apply_data_patch(item, changes):
    patch_changes = []
    prepare_patch(patch_changes, item, changes)
    if not patch_changes:
        return {}
    return _apply_patch(item, patch_changes)


def get_revision_changes(dst, src):
    return make_patch(dst, src).patch


def set_ownership(item, request):
    if not item.get('owner'):
        item.owner = request.authenticated_userid
    owner_token = generate_id()
    item.owner_token = sha512(owner_token).hexdigest()
    acc = {'token': owner_token}
    if isinstance(getattr(type(item), 'transfer_token', None), StringType):
        transfer_token = generate_id()
        item.transfer_token = sha512(transfer_token).hexdigest()
        acc['transfer'] = transfer_token
    return acc


def context_unpack(request, msg, params=None):
    if params:
        update_logging_context(request, params)
    logging_context = request.logging_context
    journal_context = msg
    for key, value in logging_context.items():
        journal_context["JOURNAL_" + key] = value
    return journal_context


def get_content_configurator(request):
    content_type = request.path[len(ROUTE_PREFIX)+1:].split('/')[0][:-1]
    if hasattr(request, content_type):  # content is constructed
        context = getattr(request, content_type)
        return request.registry.queryMultiAdapter((context, request),
                                                  IContentConfigurator)


def error_handler(request, request_params=True):
    errors = request.errors
    params = {
        'ERROR_STATUS': errors.status
    }
    if request_params:
        params['ROLE'] = str(request.authenticated_role)
        if request.params:
            params['PARAMS'] = str(dict(request.params))
    if request.matchdict:
        for x, j in request.matchdict.items():
            params[x.upper()] = j
    request.registry.notify(ErrorDesctiptorEvent(request, params))
    LOGGER.info('Error on processing request "{}"'.format(dumps(errors, indent=4)),
                extra=context_unpack(request, {'MESSAGE_ID': 'error_handler'}, params))
    return json_error(request)


def request_params(request):
    try:
        params = NestedMultiDict(request.GET, request.POST)
    except UnicodeDecodeError:
        request.errors.add('body', 'data', 'could not decode params')
        request.errors.status = 422
        raise error_handler(request, False)
    except Exception, e:
        request.errors.add('body', str(e.__class__.__name__), str(e))
        request.errors.status = 422
        raise error_handler(request, False)
    return params


def fix_url(item, app_url):
    if isinstance(item, list):
        [
            fix_url(i, app_url)
            for i in item
            if isinstance(i, dict) or isinstance(i, list)
        ]
    elif isinstance(item, dict):
        if "format" in item and "url" in item and '?download=' in item['url']:
            path = item["url"] if item["url"].startswith('/') else '/' + '/'.join(item['url'].split('/')[5:])
            item["url"] = app_url + ROUTE_PREFIX + path
            return
        [
            fix_url(item[i], app_url)
            for i in item
            if isinstance(item[i], dict) or isinstance(item[i], list)
        ]


def upload_file(request, blacklisted_fields=DOCUMENT_BLACKLISTED_FIELDS, whitelisted_fields=DOCUMENT_WHITELISTED_FIELDS):
    first_document = request.validated['documents'][-1] if 'documents' in request.validated and request.validated['documents'] else None
    if request.content_type == 'multipart/form-data':
        data = request.validated['file']
        filename = get_filename(data)
        content_type = data.type
        in_file = data.file
    else:
        filename = first_document.title
        content_type = request.content_type
        in_file = request.body_file

    if hasattr(request.context, "documents"):
        # upload new document
        model = type(request.context).documents.model_class
    else:
        # update document
        model = type(request.context)
    document = model({'title': filename, 'format': content_type})
    document.__parent__ = request.context
    if 'document_id' in request.validated:
        document.id = request.validated['document_id']
    if first_document:
        for attr_name in type(first_document)._fields:
            if attr_name not in blacklisted_fields:
                setattr(document, attr_name, getattr(first_document, attr_name))

    key = generate_id()
    filename = "{}_{}".format(document.id, key)
    request.validated['db_doc']['_attachments'][filename] = {
        "content_type": document.format,
        "data": b64encode(in_file.read())
    }

    document_route = request.matched_route.name.replace("collection_", "")
    document_path = request.current_route_path(_route_name=document_route, document_id=document.id, _query={'download': key})
    document.url = '/' + '/'.join(document_path.split('/')[3:])
    update_logging_context(request, {'file_size': in_file.tell()})
    return document


def update_file_content_type(request):
    pass  # TODO


def get_filename(data):
    try:
        pairs = decode_header(data.filename)
    except Exception:
        pairs = None
    if not pairs:
        return data.filename
    header = pairs[0]
    if header[1]:
        return header[0].decode(header[1])
    else:
        return header[0]


def get_file(request):
    db_doc_id = request.validated['db_doc'].id
    document = request.validated['document']
    key = request.params.get('download')
    if not any([key in i.url for i in request.validated['documents']]):
        request.errors.add('url', 'download', 'Not Found')
        request.errors.status = 404
        return
    filename = "{}_{}".format(document.id, key)
    data = request.registry.db.get_attachment(db_doc_id, filename)
    if data:
        request.response.content_type = document.format.encode('utf-8')
        request.response.content_disposition = build_header(document.title, filename_compat=quote(document.title.encode('utf-8')))
        request.response.body_file = data
        return request.response
    request.errors.add('url', 'download', 'Not Found')
    request.errors.status = 404


def forbidden(request):
    request.errors.add('url', 'permission', 'Forbidden')
    request.errors.status = 403
    return error_handler(request)


def update_logging_context(request, params):
    if not request.__dict__.get('logging_context'):
        request.logging_context = {}

    for x, j in params.items():
        request.logging_context[x.upper()] = j


def raise_operation_error(request, error_handler, message):
    """
    This function mostly used in views validators to add access errors and
    raise exceptions if requested operation is forbidden.
    """
    request.errors.add('body', 'data', message)
    request.errors.status = 403
    raise error_handler(request)


class APIResource(object):

    def __init__(self, request, context):
        self.context = context
        self.request = request
        self.db = request.registry.db
        self.server_id = request.registry.server_id
        self.LOGGER = getLogger(type(self).__module__)


class APIResourceListing(APIResource):

    def __init__(self, request, context):
        super(APIResourceListing, self).__init__(request, context)
        self.server = request.registry.couchdb_server
        self.update_after = request.registry.update_after

    @json_view(permission='view_listing')
    def get(self):
        params = {}
        pparams = {}
        fields = self.request.params.get('opt_fields', '')
        if fields:
            params['opt_fields'] = fields
            pparams['opt_fields'] = fields
            fields = fields.split(',')
            view_fields = fields + ['dateModified', 'id']
        limit = self.request.params.get('limit', '')
        if limit:
            params['limit'] = limit
            pparams['limit'] = limit
        limit = int(limit) if limit.isdigit() and (100 if fields else 1000) >= int(limit) > 0 else 100
        descending = bool(self.request.params.get('descending'))
        offset = self.request.params.get('offset', '')
        if descending:
            params['descending'] = 1
        else:
            pparams['descending'] = 1
        feed = self.request.params.get('feed', '')
        view_map = self.FEED.get(feed, self.VIEW_MAP)
        changes = view_map is self.CHANGES_VIEW_MAP
        if feed and feed in self.FEED:
            params['feed'] = feed
            pparams['feed'] = feed
        mode = self.request.params.get('mode', '')
        if mode and mode in view_map:
            params['mode'] = mode
            pparams['mode'] = mode
        view_limit = limit + 1 if offset else limit
        if changes:
            if offset:
                view_offset = decrypt(self.server.uuid, self.db.name, offset)
                if view_offset and view_offset.isdigit():
                    view_offset = int(view_offset)
                else:
                    self.request.errors.add('querystring', 'offset', 'Offset expired/invalid')
                    self.request.errors.status = 404
                    raise error_handler(self.request)
            if not offset:
                view_offset = 'now' if descending else 0
        else:
            if offset:
                view_offset = offset
            else:
                view_offset = '9' if descending else ''
        list_view = view_map.get(mode, view_map[u''])
        if self.update_after:
            view = partial(list_view, self.db, limit=view_limit, startkey=view_offset, descending=descending, stale='update_after')
        else:
            view = partial(list_view, self.db, limit=view_limit, startkey=view_offset, descending=descending)
        if fields:
            if not changes and set(fields).issubset(set(self.FIELDS)):
                results = [
                    (dict([(i, j) for i, j in x.value.items() + [('id', x.id), ('dateModified', x.key)] if i in view_fields]), x.key)
                    for x in view()
                ]
            elif changes and set(fields).issubset(set(self.FIELDS)):
                results = [
                    (dict([(i, j) for i, j in x.value.items() + [('id', x.id)] if i in view_fields]), x.key)
                    for x in view()
                ]
            elif fields:
                self.LOGGER.info('Used custom fields for {} list: {}'.format(self.object_name_for_listing, ','.join(sorted(fields))),
                            extra=context_unpack(self.request, {'MESSAGE_ID': self.log_message_id}))

                results = [
                    (self.serialize_func(self.request, i[u'doc'], view_fields), i.key)
                    for i in view(include_docs=True)
                ]
        else:
            results = [
                ({'id': i.id, 'dateModified': i.value['dateModified']} if changes else {'id': i.id, 'dateModified': i.key}, i.key)
                for i in view()
            ]
        if results:
            params['offset'], pparams['offset'] = results[-1][1], results[0][1]
            if offset and view_offset == results[0][1]:
                results = results[1:]
            elif offset and view_offset != results[0][1]:
                results = results[:limit]
                params['offset'], pparams['offset'] = results[-1][1], view_offset
            results = [i[0] for i in results]
            if changes:
                params['offset'] = encrypt(self.server.uuid, self.db.name, params['offset'])
                pparams['offset'] = encrypt(self.server.uuid, self.db.name, pparams['offset'])
        else:
            params['offset'] = offset
            pparams['offset'] = offset
        data = {
            'data': results,
            'next_page': {
                "offset": params['offset'],
                "path": self.request.route_path(self.object_name_for_listing, _query=params),
                "uri": self.request.route_url(self.object_name_for_listing, _query=params)
            }
        }
        if descending or offset:
            data['prev_page'] = {
                "offset": pparams['offset'],
                "path": self.request.route_path(self.object_name_for_listing, _query=pparams),
                "uri": self.request.route_url(self.object_name_for_listing, _query=pparams)
            }
        return data


def set_modetest_titles(item):
    if not item.title or u'[ТЕСТУВАННЯ]' not in item.title:
        item.title = u'[ТЕСТУВАННЯ] {}'.format(item.title or u'')
    if not item.title_en or u'[TESTING]' not in item.title_en:
        item.title_en = u'[TESTING] {}'.format(item.title_en or u'')
    if not item.title_ru or u'[ТЕСТИРОВАНИЕ]' not in item.title_ru:
        item.title_ru = u'[ТЕСТИРОВАНИЕ] {}'.format(item.title_ru or u'')


# Schematics Serialize Functions


def serialize_document_url(document):
    url = document.url
    if not url or '?download=' not in url:
        return url
    doc_id = parse_qs(urlparse(url).query)['download'][-1]
    root = document.__parent__
    parents = []
    while root.__parent__ is not None:
        parents[0:0] = [root]
        root = root.__parent__
    request = root.request
    if not request.registry.docservice_url:
        return url
    if 'status' in parents[0] and parents[0].status in type(parents[0])._options.roles:
        role = parents[0].status
        for index, obj in enumerate(parents):
            if obj.id != url.split('/')[(index - len(parents)) * 2 - 1]:
                break
            field = url.split('/')[(index - len(parents)) * 2]
            if "_" in field:
                field = field[0] + field.title().replace("_", "")[1:]
            roles = type(obj)._options.roles
            if roles[role if role in roles else 'default'](field, []):
                return url
    if not document.hash:
        path = [i for i in urlparse(url).path.split('/') if len(i) == 32 and not set(i).difference(hexdigits)]
        return generate_docservice_url(request, doc_id, False, '{}/{}'.format(path[0], path[-1]))
    return generate_docservice_url(request, doc_id, False)