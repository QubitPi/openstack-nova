# Copyright 2012 IBM Corp.
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

from webob import exc

from nova.api.openstack.compute.schemas import fixed_ips as schema
from nova.api.openstack import wsgi
from nova.api import validation

_removal_reason = """\
This API only works with *nova-network*, which was deprecated in the
14.0.0 (Newton) release.
It fails with HTTP 404 starting from microversion 2.36.
It was removed in the 18.0.0 (Rocky) release.
"""


@validation.validated
class FixedIPController(wsgi.Controller):

    @wsgi.expected_errors((410))
    @wsgi.removed('18.0.0', _removal_reason)
    @validation.query_schema(schema.show_query)
    @validation.response_body_schema(schema.show_response)
    def show(self, req, id):
        raise exc.HTTPGone()

    @wsgi.expected_errors((410))
    @wsgi.action('reserve')
    @wsgi.removed('18.0.0', _removal_reason)
    @validation.schema(schema.reserve)
    @validation.response_body_schema(schema.reserve_response)
    def reserve(self, req, id, body):
        raise exc.HTTPGone()

    @wsgi.expected_errors((410))
    @wsgi.action('unreserve')
    @wsgi.removed('18.0.0', _removal_reason)
    @validation.schema(schema.unreserve)
    @validation.response_body_schema(schema.unreserve_response)
    def unreserve(self, req, id, body):
        raise exc.HTTPGone()
