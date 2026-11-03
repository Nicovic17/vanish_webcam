import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from local_app import license_client as licensing
from local_app import vanish_cam as app


class ClientTests(unittest.TestCase):
    def test_email_normalizes_and_rejects_invalid_document_paths(self):
        self.assertEqual(licensing.normalize_email('  Cliente+demo@Example.COM  '), 'cliente+demo@example.com')
        for value in ('', 'not-email', 'a/b@example.com', 'a@example.com/xx', 'a@x', 'a\n@x.com'):
            with self.assertRaises(licensing.LicenseError):
                licensing.normalize_email(value)

    @unittest.skipUnless(os.name == 'nt', 'Windows credentials')
    def test_credentials_are_dpapi_protected_and_roundtrip_without_plaintext(self):
        with TemporaryDirectory() as directory:
            store = licensing.ProtectedStore('demo', Path(directory))
            state = {'email':'cliente@example.com','refreshToken':'test-token-not-real','uid':'pc-a'}
            self.assertEqual(store.read(), {})
            store.save(state)
            self.assertEqual(store.read(), state)
            self.assertNotIn(b'test-token-not-real', store.path.read_bytes())
            self.assertNotIn(b'cliente@example.com', store.path.read_bytes())

    @unittest.skipUnless(os.name == 'nt', 'Windows device')
    def test_hardware_identity_is_stable_and_hashed(self):
        first = licensing.device_id()
        self.assertEqual(first, licensing.device_id())
        self.assertRegex(first, r'^[a-f0-9]{64}$')

    @unittest.skipUnless(os.name == 'nt', 'Windows mutex')
    def test_local_mutex_blocks_second_edition_until_first_closes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'identity.bin'
            first = licensing.LocalInstance(path)
            try:
                with self.assertRaises(licensing.LicenseError):
                    licensing.LocalInstance(path)
            finally:
                first.close()
            second = licensing.LocalInstance(path)
            second.close()

    def test_auth_is_anonymous_and_reuses_saved_refresh_token(self):
        store = Mock()
        store.read.return_value = {}
        auth = licensing.DeviceAuth({'apiKey':'public-key'}, store)
        with patch.object(licensing, '_json_request', return_value={
            'idToken':'token','localId':'pc-a','refreshToken':'refresh','expiresIn':'3600',
        }) as request:
            auth.authenticate()
        self.assertEqual(request.call_args.args[1], {'returnSecureToken':True})
        self.assertIn('accounts:signUp', request.call_args.args[0])
        self.assertEqual(auth.state['uid'], 'pc-a')
        with patch.object(licensing, '_json_request', return_value={
            'id_token':'next','user_id':'pc-a','refresh_token':'next-refresh','expires_in':'3600',
        }) as refresh:
            auth.authenticate()
        self.assertEqual(refresh.call_args.args[1]['refresh_token'], 'refresh')
        self.assertNotIn('password', refresh.call_args.args[1])

    def backend(self):
        auth = Mock(state={'uid':'pc-a'})
        auth.id_token.return_value = 'token'
        return licensing.FirestoreLicense({'projectId':'demo'}, auth, 'cliente@example.com', 'a'*64)

    def test_inactive_license_never_writes_a_binding(self):
        backend = self.backend()
        backend._request = Mock(return_value={'transaction':'tx'})
        backend._document = Mock(return_value={'fields':{'active':{'booleanValue':False}}})
        with self.assertRaisesRegex(licensing.LicenseError, 'non attiva'):
            backend.acquire()
        self.assertFalse(any(c.args[0] == ':commit' for c in backend._request.call_args_list))

    def test_success_commits_binding_and_session_with_server_timestamps(self):
        backend = self.backend()
        backend._request = Mock(return_value={'transaction':'tx'})
        backend._document = Mock(side_effect=[{'fields':{'active':{'booleanValue':True}}},None,None])
        deadline = backend.acquire()
        writes = next(c.args[1]['writes'] for c in backend._request.call_args_list if c.args[0] == ':commit')
        self.assertEqual(len(writes), 2)
        self.assertTrue(all(write['updateTransforms'][0]['setToServerValue'] == 'REQUEST_TIME' for write in writes))
        self.assertLessEqual(deadline - licensing.time.monotonic(), 105)

    def test_foreign_device_binding_fails_before_commit(self):
        backend = self.backend()
        backend._request = Mock(return_value={'transaction':'tx'})
        backend._document = Mock(side_effect=[{'fields':{'active':{'booleanValue':True}}},
            {'fields':{'uid':{'stringValue':'pc-b'},'deviceId':{'stringValue':'b'*64}}}])
        with self.assertRaisesRegex(licensing.LicenseError, 'altro PC'):
            backend.acquire()
        self.assertFalse(any(c.args[0] == ':commit' for c in backend._request.call_args_list))

    def test_release_does_not_delete_or_replace_other_sessions(self):
        backend = self.backend()
        backend._request = Mock()
        backend.release()
        write = backend._request.call_args.args[1]['writes'][0]
        self.assertEqual(write['currentDocument'], {'exists':True})
        self.assertEqual(write['update']['fields']['sessionId']['stringValue'], backend.session_id)
        self.assertTrue(write['update']['fields']['released']['booleanValue'])

    def test_expired_online_check_fails_closed(self):
        backend = Mock()
        session = licensing.LicenseSession(backend, deadline=20)
        with patch.object(licensing.time, 'monotonic', return_value=21):
            with self.assertRaises(licensing.LicenseError):
                session.ensure_valid()
        session.error = 'Licenza disattivata'
        with self.assertRaisesRegex(licensing.LicenseError, 'disattivata'):
            session.ensure_valid()

    def test_permanent_heartbeat_failure_stops_the_session(self):
        backend = Mock()
        backend.renew.side_effect = licensing.ServiceError('PERMISSION_DENIED')
        session = licensing.LicenseSession(backend, deadline=float('inf'))
        session.stop_event = Mock()
        session.stop_event.wait.return_value = False
        session._heartbeat()
        with self.assertRaises(licensing.LicenseError):
            session.ensure_valid()

    def test_temporary_network_failure_does_not_extend_the_lease(self):
        backend = Mock()
        backend.renew.side_effect = licensing.ServiceError('NETWORK', True)
        session = licensing.LicenseSession(backend, deadline=100)
        session.stop_event = Mock()
        session.stop_event.wait.side_effect = [False, True]
        with patch.object(licensing.time, 'monotonic', return_value=30):
            session._heartbeat()
        self.assertEqual(session.deadline, 100)
        self.assertIsNone(session.error)


class EntryPointTests(unittest.TestCase):
    def test_packaged_modes_use_license_before_camera_work(self):
        for mode in app.ALL_MODES:
            session = MagicMock()
            with patch.object(app.sys, 'argv', ['vanish_cam.py','--mode',mode]), \
                 patch.object(app.sys, 'frozen', True, create=True), \
                 patch.object(app, 'activate_license', return_value=session) as activation, \
                 patch.object(app, 'run', return_value=0) as run:
                self.assertEqual(app.main(), 0)
            activation.assert_called_once()
            run.assert_called_once_with(session)

    def test_local_python_runs_without_online_license(self):
        with patch.object(app.sys, 'argv', ['vanish_cam.py','--mode','itachi']), \
             patch.object(app.sys, 'frozen', False, create=True), \
             patch.object(app, 'activate_license') as activation, \
             patch.object(app, 'run', return_value=0) as run, \
             patch('builtins.print'):
            self.assertEqual(app.main(), 0)
        activation.assert_not_called()
        run.assert_called_once_with()

    def test_new_effect_reports_supported_full_mode_until_rules_are_deployed(self):
        for mode, expected in (('itachi', 'full'), ('naruto', 'naruto')):
            session = MagicMock()
            args = SimpleNamespace(mode=mode, camera=0, no_mirror=False)
            with patch.object(app, 'parse_args', return_value=args), \
                 patch.object(app, 'edition_modes', return_value=app.ALL_MODES), \
                 patch.object(app, 'run_camera', return_value=0):
                self.assertEqual(app.run(session), 0)
            self.assertEqual(session.backend.mode, expected)
            session.ensure_valid.assert_called()

    def test_license_denied_or_cancelled_cannot_open_camera(self):
        with patch.object(app.sys, 'argv', ['vanish_cam.py']), \
             patch.object(app.sys, 'frozen', True, create=True), \
             patch.object(app, 'activate_license', return_value=None), \
             patch.object(app, 'run') as run:
            self.assertEqual(app.main(), 0)
        run.assert_not_called()
        with patch.object(app.sys, 'argv', ['vanish_cam.py']), \
             patch.object(app.sys, 'frozen', True, create=True), \
             patch.object(app, 'activate_license', side_effect=licensing.LicenseError('Revocata')), \
             patch.object(app, 'show_license_error'), patch.object(app,'run') as run:
            self.assertEqual(app.main(), 1)
        run.assert_not_called()

    def test_self_test_can_check_resources_but_never_calls_activation(self):
        with patch.object(app.sys, 'argv', ['vanish_cam.py','--self-test']), \
             patch.object(app, 'activate_license') as activation, \
             patch.object(app, 'run', return_value=0):
            self.assertEqual(app.main(), 0)
        activation.assert_not_called()

    def test_revocation_before_send_closes_devices_and_sends_no_frame(self):
        import numpy as np
        from contextlib import ExitStack
        capture, segmenter, recognizer, virtual = Mock(), Mock(), Mock(), Mock()
        capture.read.return_value = (True, np.zeros((24, 40, 3), np.uint8))
        guard = Mock()
        guard.ensure_valid.side_effect = [None, licensing.LicenseError('Revocata')]
        args = SimpleNamespace(camera=0,width=40,height=24,fps=30,fullscreen=False,
                               no_mirror=True,gesture_debug=False)
        with ExitStack() as stack:
            stack.enter_context(patch.object(app,'download_models'))
            stack.enter_context(patch.object(app,'open_camera',return_value=capture))
            stack.enter_context(patch.object(app,'create_tasks',return_value=(segmenter,recognizer)))
            stack.enter_context(patch.object(app,'open_virtual_camera',return_value=virtual))
            for method in ('namedWindow','resizeWindow','destroyAllWindows'):
                stack.enter_context(patch.object(app.cv2,method))
            with self.assertRaisesRegex(licensing.LicenseError,'Revocata'):
                with ExitStack() as resources:
                    app.run_camera(args,resources,'normal',guard)
        virtual.send.assert_not_called()
        virtual.close.assert_called_once()
        capture.release.assert_called_once()
        recognizer.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
