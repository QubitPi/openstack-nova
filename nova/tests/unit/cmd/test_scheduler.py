# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from unittest import mock

from nova.cmd import scheduler
from nova import config
from nova import test
from nova import utils


# required because otherwise oslo early parse_args dies
@mock.patch.object(config, 'parse_args', new=lambda *args, **kwargs: None)
class TestScheduler(test.NoDBTestCase):

    @mock.patch('nova.service.Service.create')
    @mock.patch('nova.service.serve')
    @mock.patch('nova.service.wait')
    @mock.patch('oslo_concurrency.processutils.get_worker_count',
                return_value=2)
    def test_workers_defaults(self, get_worker_count, mock_wait, mock_serve,
                              service_create):
        scheduler.main()
        get_worker_count.assert_called_once_with()
        mock_serve.assert_called_once_with(
            service_create.return_value, workers=2)
        mock_wait.assert_called_once_with()

    @mock.patch('nova.service.Service.create')
    @mock.patch('nova.service.serve')
    @mock.patch('nova.service.wait')
    @mock.patch('oslo_concurrency.processutils.get_worker_count')
    def test_workers_override(self, get_worker_count, mock_wait, mock_serve,
                              service_create):
        self.flags(workers=4, group='scheduler')
        scheduler.main()
        get_worker_count.assert_not_called()
        mock_serve.assert_called_once_with(
            service_create.return_value, workers=4)
        mock_wait.assert_called_once_with()

    @mock.patch('nova.service.Service.create')
    @mock.patch('nova.service.serve')
    @mock.patch('nova.service.wait')
    def test_executors_destroyed_before_fork(
        self, mock_wait, mock_serve, service_create
    ):
        # simulate that the thread pool is initialized before the fork
        executor = utils._get_default_executor()
        sc_executor = utils.get_scatter_gather_executor()
        scheduler.main()

        mock_serve.assert_called_once_with(
            service_create.return_value, workers=mock.ANY)
        mock_wait.assert_called_once_with()
        # check that the executor was properly destroyed
        self.assertFalse(executor.alive)
        self.assertIsNone(utils.DEFAULT_EXECUTOR)
        self.assertFalse(sc_executor.alive)
        self.assertIsNone(utils.SCATTER_GATHER_EXECUTOR)
