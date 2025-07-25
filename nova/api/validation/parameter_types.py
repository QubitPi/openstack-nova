# Copyright 2014 NEC Corporation.  All rights reserved.
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
"""
Common parameter types for validating request Body.

"""

import copy
import functools
import re
import unicodedata

from nova.i18n import _
from nova.objects import tag

_REGEX_RANGE_CACHE = {}


def memorize(func):
    @functools.wraps(func)
    def memorizer(*args, **kwargs):
        global _REGEX_RANGE_CACHE
        key = "%s:%s:%s" % (func.__name__, hash(str(args)), hash(str(kwargs)))
        value = _REGEX_RANGE_CACHE.get(key)
        if value is None:
            value = func(*args, **kwargs)
            _REGEX_RANGE_CACHE[key] = value
        return value

    return memorizer


def _reset_cache():
    global _REGEX_RANGE_CACHE
    _REGEX_RANGE_CACHE = {}


def single_param(schema):
    """Macro function for use in JSONSchema to support query parameters that
    should have only one value.
    """
    ret = multi_params(schema)
    ret['maxItems'] = 1
    return ret


def multi_params(schema):
    """Macro function for use in JSONSchema to support query parameters that
    may have multiple values.
    """
    return {'type': 'array', 'items': schema}


# NOTE: We don't check actual values of queries on params
# which are defined as the following common_param.
# Please note those are for backward compatible existing
# query parameters because previously multiple parameters
# might be input and accepted.
common_query_param = multi_params({'type': 'string'})
common_query_regex_param = multi_params({'type': 'string', 'format': 'regex'})


class ValidationRegex(object):
    def __init__(self, regex, reason):
        self.regex = regex
        self.reason = reason


def _is_printable(char):
    """determine if a unicode code point is printable.

    This checks if the character is either "other" (mostly control
    codes), or a non-horizontal space. All characters that don't match
    those criteria are considered printable; that is: letters;
    combining marks; numbers; punctuation; symbols; (horizontal) space
    separators.
    """
    category = unicodedata.category(char)
    return (not category.startswith("C") and
            (not category.startswith("Z") or category == "Zs"))


def _get_all_chars():
    for i in range(0xFFFF):
        yield chr(i)


# build a regex that matches all printable characters. This allows
# spaces in the middle of the name. Also note that the regexp below
# deliberately allows the empty string. This is so only the constraint
# which enforces a minimum length for the name is triggered when an
# empty string is tested. Otherwise it is not deterministic which
# constraint fails and this causes issues for some unittests when
# PYTHONHASHSEED is set randomly.


@memorize
def _build_regex_range(ws=True, invert=False, exclude=None):
    """Build a range regex for a set of characters in utf8.

    This builds a valid range regex for characters in utf8 by
    iterating the entire space and building up a set of x-y ranges for
    all the characters we find which are valid.

    :param ws: should we include whitespace in this range.
    :param exclude: any characters we want to exclude
    :param invert: invert the logic

    The inversion is useful when we want to generate a set of ranges
    which is everything that's not a certain class. For instance,
    produce all the non printable characters as a set of ranges.
    """
    if exclude is None:
        exclude = []
    regex = ""
    # are we currently in a range
    in_range = False
    # last character we found, for closing ranges
    last = None
    # last character we added to the regex, this lets us know that we
    # already have B in the range, which means we don't need to close
    # it out with B-B. While the later seems to work, it's kind of bad form.
    last_added = None

    def valid_char(char):
        if char in exclude:
            result = False
        elif ws:
            result = _is_printable(char)
        else:
            # Zs is the unicode class for space characters, of which
            # there are about 10 in this range.
            result = _is_printable(char) and unicodedata.category(char) != 'Zs'
        if invert is True:
            return not result
        return result

    # iterate through the entire character range. in_
    for c in _get_all_chars():
        if valid_char(c):
            if not in_range:
                regex += re.escape(c)
                last_added = c
            in_range = True
        else:
            if in_range and last != last_added:
                regex += "-" + re.escape(last)
            in_range = False
        last = c
    else:
        if in_range:
            regex += "-" + re.escape(c)
    return regex


valid_name_regex_base = '^(?![%s])[%s]*(?<![%s])$'

valid_name_regex = ValidationRegex(
    valid_name_regex_base % (
        _build_regex_range(ws=False, invert=True),
        _build_regex_range(),
        _build_regex_range(ws=False, invert=True)),
    _("printable characters. Can not start or end with whitespace."))

# This regex allows leading/trailing whitespace
valid_name_leading_trailing_spaces_regex_base = (
    "^[%(ws)s]*[%(no_ws)s]+[%(ws)s]*$|"
    "^[%(ws)s]*[%(no_ws)s][%(no_ws)s%(ws)s]+[%(no_ws)s][%(ws)s]*$")

valid_az_name_regex = ValidationRegex(
    valid_name_regex_base % (
        _build_regex_range(ws=False, invert=True),
        _build_regex_range(exclude=[':']),
        _build_regex_range(ws=False, invert=True)),
    _("printable characters except :."
      "Can not start or end with whitespace."))

# az's name disallow ':'.
valid_az_name_leading_trailing_spaces_regex = ValidationRegex(
    valid_name_leading_trailing_spaces_regex_base % {
        'ws': _build_regex_range(exclude=[':']),
        'no_ws': _build_regex_range(ws=False, exclude=[':'])},
    _("printable characters except :, "
      "with at least one non space character"))

valid_name_leading_trailing_spaces_regex = ValidationRegex(
    valid_name_leading_trailing_spaces_regex_base % {
        'ws': _build_regex_range(),
        'no_ws': _build_regex_range(ws=False)},
    _("printable characters with at least one non space character"))

valid_description_regex_base = '^[%s]*$'

valid_description_regex = valid_description_regex_base % (_build_regex_range())

boolean = {
    'type': ['boolean', 'string'],
    'enum': [True, 'True', 'TRUE', 'true', '1', 'ON', 'On', 'on',
             'YES', 'Yes', 'yes',
             False, 'False', 'FALSE', 'false', '0', 'OFF', 'Off', 'off',
             'NO', 'No', 'no'],
}


name_or_none = {
    'oneOf': [
        {'type': 'string', 'minLength': 1, 'maxLength': 255},
        {'type': 'null'},
    ]
}

positive_integer = {
    'type': ['integer', 'string'],
    'pattern': '^[0-9]*$',
    'minimum': 1,
    'minLength': 1,
}

non_negative_integer = {
    'type': ['integer', 'string'],
    'pattern': '^[0-9]*$',
    'minimum': 0,
    'minLength': 1,
}

# A host-specific or leaf label.
#
# This is based on the specifications from two RFCs, RFCC 952 and RFC 1123.
#
# From RFC 952:
#
#   A "name" (Net, Host, Gateway, or Domain name) is a text string up to 24
#   characters drawn from the alphabet (A-Z), digits (0-9), minus sign (-), and
#   period (.). Note that periods are only allowed when they serve to delimit
#   components of "domain style names". (See RFC-921, "Domain Name System
#   Implementation Schedule", for background). No blank or space characters are
#   permitted as part of a name. No distinction is made between upper and lower
#   case. The first character must be an alpha character. The last character
#   must not be a minus sign or period. [...] Single character names or
#   nicknames are not allowed.
#
# From RFC 1123, which revises RFC 952:
#
#   The syntax of a legal Internet host name was specified in RFC-952 [DNS:4].
#   One aspect of host name syntax is hereby changed: the restriction on the
#   first character is relaxed to allow either a letter or a digit. Host
#   software MUST support this more liberal syntax.
#
#   Host software MUST handle host names of up to 63 characters and SHOULD
#   handle host names of up to 255 characters.
hostname = {
    'type': 'string',
    'pattern': '^[a-zA-Z0-9]+[a-zA-Z0-9-]*[a-zA-Z0-9]+$',
    'minLength': 2,
    'maxLength': 63,
}

fqdn = {
    'type': 'string',
    # NOTE: 'host' is defined in "services" table, and that
    # means a hostname. The hostname grammar in RFC952 does
    # not allow for underscores in hostnames. However, this
    # schema allows them, because it sometimes occurs in
    # real systems.
    'pattern': '^[a-zA-Z0-9-._]*$',
    'minLength': 1,
    'maxLength': 255,
}

name = {
    # NOTE: Nova v2.1 API contains some 'name' parameters such
    # as server, flavor, aggregate and so on. They are
    # stored in the DB and Nova specific parameters.
    # This definition is used for all their parameters.
    'type': 'string',
    'format': 'name',
    'minLength': 1,
    'maxLength': 255,
}

az_name = {
    'type': 'string',
    'format': 'az_name',
    'minLength': 1,
    'maxLength': 255,
}

keypair_name_special_chars = {
    'allOf': [
        name,
        {
            'type': 'string',
            'pattern': r'^[_\- a-zA-Z0-9]+$',
            'minLength': 1,
            'maxLength': 255,
        },
    ]
}

keypair_name_special_chars_v292 = {
    'allOf': [
        name,
        {
            'type': 'string',
            'pattern': r'^[_\-\@\. a-zA-Z0-9]+$',
            'minLength': 1,
            'maxLength': 255,
        },
    ]
}

az_name_with_leading_trailing_spaces = {
    'type': 'string',
    'format': 'az_name_with_leading_trailing_spaces',
    'minLength': 1,
    'maxLength': 255,
}

name_with_leading_trailing_spaces = {
    'type': 'string',
    'format': 'name_with_leading_trailing_spaces',
    'minLength': 1,
    'maxLength': 255,
}

description = {
    'type': ['string', 'null'],
    'pattern': valid_description_regex,
    'minLength': 0,
    'maxLength': 255,
}

# TODO(stephenfin): This is no longer used and should be removed
tcp_udp_port = {
    'type': ['integer', 'string'],
    'pattern': '^[0-9]*$',
    'minimum': 0,
    'maximum': 65535,
    'minLength': 1,
}

project_id = {
    'type': 'string',
    'pattern': '^[a-zA-Z0-9-]*$',
    'minLength': 1,
    'maxLength': 255,
}

user_id = {
    'type': 'string',
    'pattern': '^[a-zA-Z0-9-]*$',
    'minLength': 1,
    'maxLength': 255,
}

server_id = {
    'type': 'string',
    'format': 'uuid',
}

image_id = {
    'type': 'string',
    'format': 'uuid',
}

share_id = {
    'type': 'string', 'format': 'uuid'
}

share_tag = {
    'type': 'string', 'minLength': 1, 'maxLength': 255,
    'pattern': '^[a-zA-Z0-9-]*$'
}

share_export_location = {
    'type': 'string'
}

share_status = {
    'type': 'string',
    'enum': ['active', 'inactive', 'attaching', 'detaching', 'error']
}

image_id_or_empty_string = {
    'oneOf': [
        {'type': 'string', 'format': 'uuid'},
        {'type': 'string', 'maxLength': 0},
    ]
}

volume_id = {
    'type': 'string',
    'format': 'uuid',
}

attachment_id = {
    'type': 'string',
    'format': 'uuid',
}

volume_type = {
    'type': ['string', 'null'],
    'minLength': 0,
    'maxLength': 255,
}

network_id = {
    'type': 'string',
    'format': 'uuid',
}

network_port_id = {
    'type': 'string',
    'format': 'uuid',
}

admin_password = {
    # NOTE: admin_password is the admin password of a server
    # instance, and it is not stored into nova's data base.
    # In addition, users set sometimes long/strange string
    # as password. It is unnecessary to limit string length
    # and string pattern.
    'type': 'string',
}

flavor_ref = {
    'type': ['string', 'integer'], 'minLength': 1
}

metadata = {
    'type': 'object',
    'patternProperties': {
        '^[a-zA-Z0-9-_:. ]{1,255}$': {
            'type': 'string', 'maxLength': 255
        }
    },
    'additionalProperties': False
}

metadata_with_null = copy.deepcopy(metadata)
metadata_with_null['patternProperties']['^[a-zA-Z0-9-_:. ]{1,255}$']['type'] =\
    ['string', 'null']

mac_address = {
    'type': 'string',
    'pattern': '^([0-9a-fA-F]{2})(:[0-9a-fA-F]{2}){5}$'
}

ip_address = {
    'type': 'string',
    'oneOf': [
        {'format': 'ipv4'},
        {'format': 'ipv6'}
    ]
}

ipv4 = {
    'type': 'string', 'format': 'ipv4'
}

ipv6 = {
    'type': 'string', 'format': 'ipv6'
}

cidr = {
    'type': 'string', 'format': 'cidr'
}

volume_size = {
    'type': ['integer', 'string'],
    'pattern': '^[0-9]+$',
    'minimum': 1,
    # maximum's value is limited to db constant's MAX_INT
    # (in nova/db/constants.py)
    'maximum': 0x7FFFFFFF
}

disk_config = {
    'type': 'string',
    'enum': ['AUTO', 'MANUAL']
}

accessIPv4 = {
    'type': 'string',
    'format': 'ipv4',
}

accessIPv6 = {
    'type': 'string',
    'format': 'ipv6',
}

flavor_param_positive = copy.deepcopy(volume_size)

flavor_param_non_negative = copy.deepcopy(volume_size)
flavor_param_non_negative['minimum'] = 0

personality = {
    'type': 'array',
    'items': {
        'type': 'object',
        'properties': {
            'path': {'type': 'string'},
            'contents': {
                'type': 'string',
                'format': 'base64'
            }
        },
        'additionalProperties': False,
    }
}

tag = {
    "type": "string",
    "pattern": '^[^,/]*$',
    "minLength": 1,
    "maxLength": tag.MAX_TAG_LENGTH,
}

pagination_parameters = {
    'limit': multi_params(non_negative_integer),
    'marker': multi_params({'type': 'string'})
}

# The trusted_certs list is restricted to a maximum of 50 IDs.
# "null" is allowed to unset/reset trusted certs during rebuild.
trusted_certs = {
    "type": ["array", "null"],
    "minItems": 1,
    "maxItems": 50,
    "uniqueItems": True,
    "items": {
        "type": "string",
        "minLength": 1,
    }
}
