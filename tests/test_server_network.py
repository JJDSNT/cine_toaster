import os
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from cine_toaster.server_network import _local_addresses, _windows_network, startup_urls


class StartupNetworkTests(unittest.TestCase):
    def test_server_prints_discovered_urls_for_the_actual_bound_port(self):
        from cine_toaster.web import serve_project

        server = MagicMock()
        server.server_address = ('0.0.0.0', 9876)
        server.serve_forever.side_effect = KeyboardInterrupt
        output = io.StringIO()
        with patch('cine_toaster.web.ThreadingHTTPServer', return_value=server), \
             patch('cine_toaster.web.ProjectIndex'), \
             patch('cine_toaster.jobs.JobManager'), \
             patch('cine_toaster.workflows.attach'), \
             patch('cine_toaster.server_network.startup_urls', return_value=['LAN URL: discovered']) as urls, \
             redirect_stdout(output):
            serve_project(Path('/film'), host='0.0.0.0', port=0)
        urls.assert_called_once_with('0.0.0.0', 9876)
        self.assertIn('LAN URL: discovered', output.getvalue())
        server.server_close.assert_called_once()

    def test_loopback_does_not_claim_or_probe_lan(self):
        with patch('cine_toaster.server_network._local_addresses') as discover:
            text = '\n'.join(startup_urls('127.0.0.1', 8787))
        discover.assert_not_called()
        self.assertIn('Local access only', text)
        self.assertIn('--host 0.0.0.0', text)

    @patch.dict(os.environ, {}, clear=True)
    @patch('cine_toaster.server_network.platform.release', return_value='Linux')
    @patch('cine_toaster.server_network._local_addresses', return_value=['192.168.1.2'])
    def test_wildcard_reports_actual_url_not_bind(self, *_):
        text = '\n'.join(startup_urls('0.0.0.0', 9000))
        self.assertIn('LAN URL: http://192.168.1.2:9000/app/creation.html', text)
        self.assertNotIn('http://0.0.0.0', text)
        self.assertIn('no authentication', text)
        self.assertIn('not verified', text)

    @patch.dict(os.environ, {'WSL_DISTRO_NAME': 'Ubuntu'})
    @patch('cine_toaster.server_network._local_addresses', return_value=['172.28.1.2'])
    @patch('cine_toaster.server_network._windows_network')
    def test_wsl_checks_actual_forward_destination_and_listener(self, windows, *_):
        windows.return_value = {'addresses': ['192.168.1.2'], 'listeners': ['192.168.1.2'],
                                'forwarding': ['192.168.1.2 8787 172.28.1.2 8787']}
        text = '\n'.join(startup_urls('0.0.0.0', 8787))
        self.assertIn('LAN URL: http://192.168.1.2:8787', text)
        self.assertIn('forwarding/listener detected', text)
        self.assertIn('phone access are not verified', text)
        windows.return_value['forwarding'] = ['192.168.1.2 8787 172.28.1.99 8787']
        self.assertIn('No matching Windows', '\n'.join(startup_urls('0.0.0.0', 8787)))
        windows.return_value['forwarding'] = ['192.168.1.2 8787 172.28.1.2 8787']
        windows.return_value['listeners'] = ['127.0.0.1']
        self.assertIn('No matching Windows', '\n'.join(startup_urls('0.0.0.0', 8787)))

    @patch.dict(os.environ, {'WSL_DISTRO_NAME': 'Ubuntu'})
    @patch('cine_toaster.server_network._local_addresses', return_value=['172.28.1.2'])
    @patch('cine_toaster.server_network._windows_network', side_effect=OSError('missing'))
    def test_unavailable_windows_tools_do_not_break_launch(self, *_):
        text = '\n'.join(startup_urls('0.0.0.0', 8787))
        self.assertIn('Windows LAN check unavailable', text)
        self.assertIn('WSL address (not necessarily reachable from LAN)', text)

    @patch.dict(os.environ, {}, clear=True)
    @patch('cine_toaster.server_network.platform.release', return_value='Linux')
    @patch('cine_toaster.server_network._local_addresses')
    def test_explicit_bind_does_not_advertise_other_interfaces(self, discover, *_):
        text = '\n'.join(startup_urls('192.168.1.3', 8787))
        discover.assert_not_called()
        self.assertIn('http://192.168.1.3:8787', text)

    @patch('cine_toaster.server_network.shutil.which', return_value='powershell.exe')
    @patch('cine_toaster.server_network.subprocess.run')
    def test_windows_probe_is_bounded_read_only_and_structured(self, run, *_):
        run.return_value.stdout = '{"addresses": ["192.168.1.2"], "listeners": [], "forwarding": []}'
        self.assertEqual(_windows_network(8787)['addresses'], ['192.168.1.2'])
        args, kwargs = run.call_args
        self.assertEqual(kwargs['timeout'], 8)
        script = args[0][-1]
        self.assertIn('$_.Port -eq 8787', script)
        self.assertIn('portproxy show', script)
        self.assertNotIn('New-NetFirewallRule', script)
        self.assertNotIn('portproxy add', script)

    @patch('cine_toaster.server_network.subprocess.run', side_effect=FileNotFoundError)
    @patch('cine_toaster.server_network.socket.socket')
    def test_address_discovery_degrades_without_ip_utility(self, socket, *_):
        socket.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.4', 1234)
        self.assertEqual(_local_addresses(), ['192.168.1.4'])
        socket.side_effect = OSError('offline')
        self.assertEqual(_local_addresses(), [])
