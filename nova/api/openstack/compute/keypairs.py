# Copyright 2011 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Keypair management extension."""

import webob
import webob.exc

from nova.api.openstack import api_version_request
from nova.api.openstack import common
from nova.api.openstack.compute.schemas import keypairs as schema
from nova.api.openstack.compute.views import keypairs as keypairs_view
from nova.api.openstack import wsgi
from nova.api import validation
from nova.compute import api as compute_api
from nova import exception
from nova.objects import keypair as keypair_obj
from nova.policies import keypairs as kp_policies


@validation.validated
class KeypairController(wsgi.Controller):

    """Keypair API controller for the OpenStack API."""

    _view_builder_class = keypairs_view.ViewBuilder

    def __init__(self):
        super(KeypairController, self).__init__()
        self.api = compute_api.KeypairAPI()

    @wsgi.response(200, "2.0", "2.1")
    @wsgi.response(201, "2.2")
    @wsgi.expected_errors((400, 403, 409))
    @validation.schema(schema.create_v20, "2.0", "2.0")
    @validation.schema(schema.create, "2.1", "2.1")
    @validation.schema(schema.create_v22, "2.2", "2.9")
    @validation.schema(schema.create_v210, "2.10", "2.91")
    @validation.schema(schema.create_v292, "2.92")
    @validation.response_body_schema(schema.create_response, "2.0", "2.1")
    @validation.response_body_schema(schema.create_response_v22, "2.2", "2.91")
    @validation.response_body_schema(schema.create_response_v292, "2.92")
    def create(self, req, body):
        """Create or import keypair.

        Sending name will generate a key and return private_key and
        fingerprint. You can send a public_key to add an existing ssh key.

        Starting in API microversion 2.2, keypairs will have the type ssh or
        x509, specified by type.

        Starting in API microversion 2.10, you can request a user if you are an
        admin.

        Starting in API microversion 2.91, keypair generation is no longer
        permitted.
        """
        key_type = False
        if api_version_request.is_supported(req, '2.2'):
            key_type = True

        user_id = None
        if api_version_request.is_supported(req, '2.10'):
            # handle optional user-id for admin only
            user_id = body['keypair'].get('user_id')

        return self._create(req, body, key_type=key_type, user_id=user_id)

    def _create(self, req, body, user_id=None, key_type=False):
        context = req.environ['nova.context']
        params = body['keypair']
        name = common.normalize_name(params['name'])
        key_type_value = params.get('type', keypair_obj.KEYPAIR_TYPE_SSH)
        user_id = user_id or context.user_id
        context.can(kp_policies.POLICY_ROOT % 'create',
                    target={'user_id': user_id})

        try:
            if 'public_key' in params:
                keypair = self.api.import_key_pair(
                    context, user_id, name, params['public_key'],
                    key_type_value)
                return_priv_key = False
            else:
                # public_key is a required field starting with 2.92 so this
                # generation should only happen with older versions.
                keypair, private_key = self.api.create_key_pair(
                    context, user_id, name, key_type_value)
                keypair['private_key'] = private_key
                return_priv_key = True
        except exception.KeypairLimitExceeded as e:
            raise webob.exc.HTTPForbidden(explanation=str(e))
        except exception.InvalidKeypair as exc:
            raise webob.exc.HTTPBadRequest(explanation=exc.format_message())
        except exception.KeyPairExists as exc:
            raise webob.exc.HTTPConflict(explanation=exc.format_message())

        return self._view_builder.create(keypair,
                                         private_key=return_priv_key,
                                         key_type=key_type)

    def _get_user_id(self, req):
        if 'user_id' in req.GET.keys():
            user_id = req.GET.getall('user_id')[0]
            return user_id

    @wsgi.response(202, '2.0', '2.1')
    @wsgi.response(204, '2.2')
    @validation.query_schema(schema.delete_query_schema_v20, '2.0', '2.9')
    @validation.query_schema(schema.delete_query_schema_v210, '2.10', '2.74')
    @validation.query_schema(schema.delete_query_schema_v275, '2.75')
    @validation.response_body_schema(schema.delete_response)
    @wsgi.expected_errors(404)
    def delete(self, req, id):
        user_id = None
        if api_version_request.is_supported(req, '2.10'):
            # handle optional user-id for admin only
            user_id = self._get_user_id(req)

        self._delete(req, id, user_id=user_id)

    def _delete(self, req, id, user_id=None):
        """Delete a keypair with a given name."""
        context = req.environ['nova.context']
        # handle optional user-id for admin only
        user_id = user_id or context.user_id
        context.can(kp_policies.POLICY_ROOT % 'delete',
                    target={'user_id': user_id})
        try:
            self.api.delete_key_pair(context, user_id, id)
        except exception.KeypairNotFound as exc:
            raise webob.exc.HTTPNotFound(explanation=exc.format_message())

    @validation.query_schema(schema.show_query_schema_v20, '2.0', '2.9')
    @validation.query_schema(schema.show_query_schema_v210, '2.10', '2.74')
    @validation.query_schema(schema.show_query_schema_v275, '2.75')
    @validation.response_body_schema(schema.show_response, '2.0', '2.1')
    @validation.response_body_schema(schema.show_response_v22, '2.2')
    @wsgi.expected_errors(404)
    def show(self, req, id):
        key_type = False
        if api_version_request.is_supported(req, '2.2'):
            key_type = True

        user_id = None
        if api_version_request.is_supported(req, '2.10'):
            # handle optional user-id for admin only
            user_id = self._get_user_id(req)

        return self._show(req, id, key_type=key_type, user_id=user_id)

    def _show(self, req, id, key_type=False, user_id=None):
        """Return data for the given key name."""
        context = req.environ['nova.context']
        user_id = user_id or context.user_id
        context.can(kp_policies.POLICY_ROOT % 'show',
                    target={'user_id': user_id})

        try:
            keypair = self.api.get_key_pair(context, user_id, id)
        except exception.KeypairNotFound as exc:
            raise webob.exc.HTTPNotFound(explanation=exc.format_message())
        return self._view_builder.show(keypair, key_type=key_type)

    @validation.query_schema(schema.index_query_schema_v20, '2.0', '2.9')
    @validation.query_schema(schema.index_query_schema_v210, '2.10', '2.34')
    @validation.query_schema(schema.index_query_schema_v235, '2.35', '2.74')
    @validation.query_schema(schema.index_query_schema_v275, '2.75')
    @validation.response_body_schema(schema.index_response, '2.0', '2.1')
    @validation.response_body_schema(schema.index_response_v22, '2.2', '2.34')
    @validation.response_body_schema(schema.index_response_v235, '2.35')
    @wsgi.expected_errors((), '2.0', '2.9')
    @wsgi.expected_errors(400, '2.10')
    def index(self, req):
        key_type = False
        if api_version_request.is_supported(req, '2.2'):
            key_type = True

        user_id = None
        if api_version_request.is_supported(req, '2.10'):
            # handle optional user-id for admin only
            user_id = self._get_user_id(req)

        links = False
        if api_version_request.is_supported(req, '2.35'):
            links = True

        # TODO(stephenfin): Remove deleted, deleted_at, and updated_at from
        # response in future microversion.
        return self._index(
            req, key_type=key_type, user_id=user_id, links=links
        )

    def _index(self, req, key_type=False, user_id=None, links=False):
        """List of keypairs for a user."""
        context = req.environ['nova.context']
        user_id = user_id or context.user_id
        context.can(kp_policies.POLICY_ROOT % 'index',
                    target={'user_id': user_id})

        if api_version_request.is_supported(req, '2.35'):
            limit, marker = common.get_limit_and_marker(req)
        else:
            limit = marker = None

        try:
            key_pairs = self.api.get_key_pairs(
                context, user_id, limit=limit, marker=marker)
        except exception.MarkerNotFound as e:
            raise webob.exc.HTTPBadRequest(explanation=e.format_message())

        return self._view_builder.index(req, key_pairs, key_type=key_type,
                                        links=links)
