# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
This provides a sphinx extension able to list the implemented versioned
notifications into the developer documentation.

It is used via a single directive in the .rst file

  .. versioned_notifications::

"""
import os

from docutils import nodes
from docutils.parsers import rst
import importlib
from oslo_serialization import jsonutils
import pkgutil

from nova.notifications.objects import base as notification
from nova.objects import base
from nova.tests import json_ref
import nova.utils


class VersionedNotificationDirective(rst.Directive):

    SAMPLE_ROOT = '../../doc/notification_samples/'
    TOGGLE_SCRIPT = """
<!-- jQuery -->
<script type="text/javascript" src="../_static/js/jquery-3.2.1.min.js">
</script>

<script>
jQuery(document).ready(function(){
    jQuery('#%s-div').toggle('show');
    jQuery('#%s-hideshow').on('click', function(event) {
        jQuery('#%s-div').toggle('show');
    });
});
</script>
"""

    def run(self):
        notifications = self._collect_notifications()
        return self._build_markup(notifications)

    def _import_all_notification_packages(self):
        list(map(lambda module: importlib.import_module(module),
                 ('nova.notifications.objects.' + name for _, name, _ in
                  pkgutil.iter_modules(nova.notifications.objects.__path__))))

    def _collect_notifications(self):
        # If you do not see your notification sample showing up in the docs
        # be sure that the sample filename matches what is registered on the
        # versioned notification object class using the
        # @base.notification_sample decorator.
        self._import_all_notification_packages()
        base.NovaObjectRegistry.register_notification_objects()
        notifications = {}
        ovos = base.NovaObjectRegistry.obj_classes()
        for name, cls in ovos.items():
            cls = cls[0]
            if (issubclass(cls, notification.NotificationBase) and
                    cls != notification.NotificationBase):

                payload_name = cls.fields['payload'].objname
                payload_cls = ovos[payload_name][0]
                for sample in cls.samples:
                    if sample in notifications:
                        raise ValueError('Duplicated usage of %s '
                                         'sample file detected' % sample)

                    notifications[sample] = ((cls.__name__,
                                              payload_cls.__name__,
                                              sample))
        return sorted(notifications.values())

    def _build_markup(self, notifications):
        content = []
        cols = ['Event type', 'Notification class', 'Payload class', 'Sample']
        table = nodes.table()
        content.append(table)
        group = nodes.tgroup(cols=len(cols))
        table.append(group)

        head = nodes.thead()
        group.append(head)

        for _ in cols:
            group.append(nodes.colspec(colwidth=1))

        body = nodes.tbody()
        group.append(body)

        # fill the table header
        row = nodes.row()
        body.append(row)
        for col_name in cols:
            col = nodes.entry()
            row.append(col)
            text = nodes.strong(text=col_name)
            col.append(text)

        # fill the table content, one notification per row
        for name, payload, sample_file in notifications:
            event_type = sample_file[0: -5].replace('-', '.')

            row = nodes.row()
            body.append(row)
            col = nodes.entry()
            row.append(col)
            text = nodes.literal(text=event_type)
            col.append(text)

            col = nodes.entry()
            row.append(col)
            text = nodes.literal(text=name)
            col.append(text)

            col = nodes.entry()
            row.append(col)
            text = nodes.literal(text=payload)
            col.append(text)

            col = nodes.entry()
            row.append(col)

            with open(os.path.join(self.SAMPLE_ROOT, sample_file), 'r') as f:
                sample_content = f.read()

            sample_obj = jsonutils.loads(sample_content)
            sample_obj = json_ref.resolve_refs(
                sample_obj,
                base_path=os.path.abspath(self.SAMPLE_ROOT))
            sample_content = jsonutils.dumps(sample_obj,
                                             sort_keys=True, indent=4,
                                             separators=(',', ': '))

            event_type = sample_file[0: -5]
            html_str = self.TOGGLE_SCRIPT % ((event_type, ) * 3)
            html_str += ("<input type='button' id='%s-hideshow' "
                         "value='hide/show sample'>" % event_type)
            html_str += ("<div id='%s-div'><pre>%s</pre></div>"
                         % (event_type, sample_content))

            raw = nodes.raw('', html_str, format="html")
            col.append(raw)

        return content


def setup(app):
    app.add_directive(
        'versioned_notifications', VersionedNotificationDirective)
    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
