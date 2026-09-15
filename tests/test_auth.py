import os
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {"TIMETABLE_AUTH_ENABLED": "0"}):
    from app import create_app
from auth import database
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse


class AuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "auth.db")
        self.env = {
            "TIMETABLE_AUTH_ENABLED": "1",
            "TIMETABLE_SETUP_ENABLED": "1",
            "TIMETABLE_AUTH_DB_PATH": self.path,
            "SECRET_KEY": "test-only-secret-" * 4,
            "PASSKEY_SETUP_TOKEN": "test-only-setup-" * 4,
            "WEBAUTHN_RP_ID": "example.com",
            "WEBAUTHN_ORIGIN": "https://example.com",
            "TIMETABLE_SESSION_COOKIE_PATH": "/",
            "TIMETABLE_SESSION_HOURS": "16",
        }
        self.app = self.make_app()
        self.client = self.app.test_client()

    def make_app(self, updates=None, removed=()):
        env = dict(self.env, **(updates or {}))
        for key in removed:
            env.pop(key, None)
        # Isolate test configuration from both machine environment and local .env.
        with patch.dict(os.environ, env, clear=True), patch("app.load_dotenv"):
            app = create_app()
        app.config["TESTING"] = True
        return app

    def get(self, path, **kwargs):
        return self.client.get(path, base_url="https://example.com", **kwargs)

    def token(self):
        self.get("/login", follow_redirects=True)
        with self.client.session_transaction(base_url="https://example.com") as session:
            return session["csrf_token"]

    def post(self, path, **kwargs):
        headers = {"X-CSRF-Token": self.token(), "Origin": "https://example.com"}
        headers.update(kwargs.pop("headers", {}))
        return self.client.post(path, base_url="https://example.com", headers=headers, **kwargs)

    def seed(self):
        with database(self.path) as db:
            db.execute("INSERT INTO credentials (credential_id, credential_public_key, sign_count) VALUES (?, ?, ?)",
                       (b"test-credential", b"test-public-key", 7))

    def rows(self):
        with database(self.path) as db:
            return [tuple(row) for row in db.execute("SELECT credential_id, credential_public_key, sign_count FROM credentials")]

    def authorize_setup(self):
        self.assertEqual(302, self.post("/setup", data={"setup_token": self.env["PASSKEY_SETUP_TOKEN"]}).status_code)

    def start_login(self):
        self.seed()
        response = self.post("/auth/login/options")
        self.assertEqual(200, response.status_code)
        return {"id": bytes_to_base64url(b"test-credential"), "response": {}}

    def assert_consumed(self):
        with self.client.session_transaction(base_url="https://example.com") as session:
            self.assertNotIn("challenge", session)
            self.assertNotIn("ceremony", session)

    def test_auth_off_requires_no_other_settings_or_db(self):
        with patch.dict(os.environ, {"TIMETABLE_AUTH_ENABLED": "0"}, clear=True), patch("app.load_dotenv"):
            app = create_app()
        client = app.test_client()
        self.assertEqual(200, client.get("/").status_code)
        self.assertEqual(404, client.get("/setup").status_code)
        self.assertNotIn("AUTH_DB_PATH", app.config)
        self.assertNotIn("logout", client.get("/").get_data(as_text=True))

    def test_auth_defaults_on_and_only_zero_disables(self):
        for value in [None, "false", "", "1"]:
            with self.subTest(value=value):
                app = self.make_app({"TIMETABLE_AUTH_ENABLED": value} if value is not None else {},
                                    removed=("TIMETABLE_AUTH_ENABLED",) if value is None else ())
                self.assertEqual(302, app.test_client().get("/").status_code)

    def test_unauthenticated_default_deny_and_public_static(self):
        for path in ["/", "/unknown", "/future-private-route"]:
            response = self.get(path)
            self.assertEqual(302, response.status_code)
            self.assertEqual("/login", response.location)
        with self.get("/static/auth.js") as response:
            self.assertEqual(200, response.status_code)

    def test_authenticated_can_search_and_logout_is_present(self):
        with self.client.session_transaction(base_url="https://example.com") as session:
            session.update(authenticated=True, authenticated_at=time.time())
            session.permanent = True
        response = self.post("/", data={"direction": "return", "target_time": "18:00"})
        self.assertEqual(200, response.status_code)
        self.assertIn('action="/logout"', response.get_data(as_text=True))

    def test_missing_db_fails_startup(self):
        with self.assertRaisesRegex(RuntimeError, "TIMETABLE_AUTH_DB_PATH"):
            self.make_app(removed=("TIMETABLE_AUTH_DB_PATH",))

    def test_missing_secret_fails_startup(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            self.make_app(removed=("SECRET_KEY",))

    def test_relative_db_path_is_resolved_from_app_root(self):
        app = self.make_app(
            {"TIMETABLE_AUTH_DB_PATH": "test-auth.db"}
        )

        expected = Path(app.root_path) / "test-auth.db"

        self.assertEqual(
            str(expected.resolve()),
            app.config["AUTH_DB_PATH"],
        )

        expected.unlink(missing_ok=True)

    def test_setup_disabled_without_registered_credential_fails_startup(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "No registered Passkey"
        ):
            self.make_app(
                {"TIMETABLE_SETUP_ENABLED": "0"}
            )

    def test_setup_disabled_without_registered_credential_fails_startup(self):
        empty_db = str(
            Path(self.directory.name) / "empty-auth.db"
        )

        with self.assertRaisesRegex(
                RuntimeError,
                "No registered Passkey"
        ):
            self.make_app({
                "TIMETABLE_AUTH_DB_PATH": empty_db,
                "TIMETABLE_SETUP_ENABLED": "0",
            })

    def test_db_permission_failure_is_clear_without_path_disclosure(self):
        with patch("auth.sqlite3.connect", side_effect=sqlite3.OperationalError("sensitive path")):
            with self.assertRaisesRegex(RuntimeError, "read/write") as caught:
                self.make_app()
        self.assertNotIn("sensitive path", str(caught.exception))

    def test_owner_handle_is_random_and_persistent_across_apps(self):
        with database(self.path) as db:
            first = db.execute("SELECT user_handle FROM auth_owner").fetchone()[0]
        self.assertEqual(32, len(first))
        self.seed()
        self.app = None
        app2 = self.make_app(
            {"TIMETABLE_SETUP_ENABLED": "0"},
            removed=("PASSKEY_SETUP_TOKEN",),
        )
        with database(app2.config["AUTH_DB_PATH"]) as db:
            self.assertEqual(first, db.execute("SELECT user_handle FROM auth_owner").fetchone()[0])
        self.assertEqual([(b"test-credential", b"test-public-key", 7)], self.rows())
        self.client = app2.test_client()
        self.assertEqual(200, self.post("/auth/login/options").status_code)

    def test_setup_disabled_blocks_registration_with_registered_credential(self):
        # 先に登録済みPasskeyを作る
        self.seed()

        # セットアップを無効にした状態で再起動
        app = self.make_app({"TIMETABLE_SETUP_ENABLED": "0"})
        client = app.test_client()

        response = client.get(
            "/setup",
            base_url="https://example.com",
        )

        self.assertEqual(403, response.status_code)

        with patch("auth.generate_registration_options") as generate:
            with client.session_transaction(
                    base_url="https://example.com"
            ) as session:
                session["csrf_token"] = "test-csrf"

            response = client.post(
                "/auth/register/options",
                base_url="https://example.com",
                headers={
                    "X-CSRF-Token": "test-csrf",
                    "Origin": "https://example.com",
                },
            )

        self.assertEqual(403, response.status_code)
        generate.assert_not_called()

    def test_setup_disabled_does_not_disable_normal_login(self):
        self.seed()

        app = self.make_app({"TIMETABLE_SETUP_ENABLED": "0"})
        client = app.test_client()

        with client.session_transaction(
                base_url="https://example.com"
        ) as session:
            session["csrf_token"] = "test-csrf"

        response = client.post(
            "/auth/login/options",
            base_url="https://example.com",
            headers={
                "X-CSRF-Token": "test-csrf",
                "Origin": "https://example.com",
            },
        )

        self.assertEqual(200, response.status_code)

    def test_setup_closed_after_registration_for_get_post_and_api(self):
        self.authorize_setup()
        self.seed()
        self.assertEqual(403, self.get("/setup").status_code)
        self.assertEqual(403, self.post("/setup", data={"setup_token": self.env["PASSKEY_SETUP_TOKEN"]}).status_code)
        self.assertEqual(403, self.post("/auth/register/options").status_code)

    def test_wrong_setup_token_and_query_cannot_authorize(self):
        self.assertEqual(403, self.post("/setup", data={"setup_token": "wrong"}).status_code)
        self.get("/setup", query_string={"token": self.env["PASSKEY_SETUP_TOKEN"]})
        self.assertEqual(403, self.post("/auth/register/options").status_code)

    def test_setup_authorization_expires(self):
        self.authorize_setup()
        with patch("auth.time.time", return_value=time.time() + 301):
            self.assertEqual(403, self.post("/auth/register/options").status_code)

    def test_registration_verification_success_stores_only_public_credential(self):
        self.authorize_setup()
        options = self.post("/auth/register/options").get_json()
        self.assertEqual("required", options["authenticatorSelection"]["userVerification"])
        verified = SimpleNamespace(credential_id=b"registered", credential_public_key=b"public-key", sign_count=0)
        with patch("auth.verify_registration_response", return_value=verified) as verify:
            response = self.post("/auth/register/verify", json={"response": {"transports": ["internal"]}})
        self.assertEqual(200, response.status_code)
        self.assertEqual([(b"registered", b"public-key", 0)], self.rows())
        self.assertTrue(verify.call_args.kwargs["require_user_verification"])
        self.assertEqual("https://example.com", verify.call_args.kwargs["expected_origin"])
        self.assertEqual("example.com", verify.call_args.kwargs["expected_rp_id"])
        self.assert_consumed()
        with self.client.session_transaction(base_url="https://example.com") as session:
            self.assertEqual({"authenticated", "authenticated_at", "_permanent"}, set(session))

    def test_registration_failure_consumes_challenge_and_does_not_register(self):
        self.authorize_setup()
        self.post("/auth/register/options")
        with patch("auth.verify_registration_response", side_effect=InvalidRegistrationResponse("private detail")):
            response = self.post("/auth/register/verify", json={})
        self.assertEqual(400, response.status_code)
        self.assertNotIn("private detail", response.get_data(as_text=True))
        self.assertEqual([], self.rows())
        self.assert_consumed()

    def test_racing_setup_cannot_register_second_credential(self):
        self.authorize_setup()
        self.post("/auth/register/options")
        def racing_verification(**kwargs):
            self.seed()
            return SimpleNamespace(credential_id=b"second", credential_public_key=b"public", sign_count=0)
        with patch("auth.verify_registration_response", side_effect=racing_verification):
            self.assertEqual(400, self.post("/auth/register/verify", json={}).status_code)
        self.assertEqual(1, len(self.rows()))

    def test_login_success_updates_count_and_session_cookie(self):
        credential = self.start_login()
        with patch("auth.verify_authentication_response", return_value=SimpleNamespace(new_sign_count=8)) as verify:
            response = self.post("/auth/login/verify", json=credential)
        self.assertEqual(200, response.status_code)
        self.assertEqual(8, self.rows()[0][2])
        args = verify.call_args.kwargs
        self.assertEqual(7, args["credential_current_sign_count"])
        self.assertEqual(b"test-public-key", args["credential_public_key"])
        self.assertTrue(args["require_user_verification"])
        self.assertEqual("example.com", args["expected_rp_id"])
        self.assertEqual("https://example.com", args["expected_origin"])
        cookie = response.headers["Set-Cookie"]
        for value in ["timetable_session=", "Secure", "HttpOnly", "SameSite=Lax", "Expires=", "Path=/"]:
            self.assertIn(value, cookie)
        self.assertFalse(self.app.config["SESSION_REFRESH_EACH_REQUEST"])
        self.assertEqual(16 * 3600, self.app.permanent_session_lifetime.total_seconds())
        self.assert_consumed()

    def test_failed_login_does_not_register_or_update_count(self):
        credential = self.start_login()
        with patch("auth.verify_authentication_response", side_effect=InvalidAuthenticationResponse("private detail")):
            response = self.post("/auth/login/verify", json=credential)
        self.assertEqual(400, response.status_code)
        self.assertEqual(7, self.rows()[0][2])
        self.assertEqual(1, len(self.rows()))
        self.assert_consumed()
        self.assertEqual(302, self.get("/").status_code)

    def test_unknown_credential_is_rejected_before_library_verification(self):
        self.start_login()
        with patch("auth.verify_authentication_response") as verify:
            response = self.post("/auth/login/verify", json={"id": bytes_to_base64url(b"unknown"), "response": {}})
        self.assertEqual(400, response.status_code)
        verify.assert_not_called()
        self.assertEqual(1, len(self.rows()))
        self.assert_consumed()

    def test_malformed_response_consumes_challenge(self):
        self.start_login()
        self.assertEqual(400, self.post("/auth/login/verify", json={"id": "abc", "response": []}).status_code)
        self.assert_consumed()

    def test_old_cookie_cannot_replay_consumed_challenge(self):
        credential = self.start_login()
        cookie = self.client.get_cookie("timetable_session", domain="example.com").value
        with patch("auth.verify_authentication_response", side_effect=InvalidAuthenticationResponse("failed")):
            self.post("/auth/login/verify", json=credential)
        self.client.set_cookie("timetable_session", cookie, domain="example.com")
        with patch("auth.verify_authentication_response") as verify:
            self.assertEqual(400, self.post("/auth/login/verify", json=credential).status_code)
        verify.assert_not_called()

    def test_expired_challenge_is_rejected(self):
        credential = self.start_login()
        with database(self.path) as db:
            db.execute("UPDATE auth_challenges SET expires_at = 0")
        with patch("auth.verify_authentication_response") as verify:
            self.assertEqual(400, self.post("/auth/login/verify", json=credential).status_code)
        verify.assert_not_called()
        self.assert_consumed()

    def test_logout_clears_session_with_post_only(self):
        with self.client.session_transaction(base_url="https://example.com") as session:
            session.update(authenticated=True, authenticated_at=time.time(), csrf_token="csrf")
        self.assertEqual(405, self.get("/logout").status_code)
        response = self.post("/logout")
        self.assertEqual("/login", response.location)
        with self.client.session_transaction(base_url="https://example.com") as session:
            self.assertEqual({}, dict(session))

    def test_absolute_session_expiry_does_not_slide(self):
        issued = time.time() - 16 * 3600 - 1
        with self.client.session_transaction(base_url="https://example.com") as session:
            session.update(authenticated=True, authenticated_at=issued)
            session.permanent = True
        self.assertEqual(302, self.get("/").status_code)
        with self.client.session_transaction(base_url="https://example.com") as session:
            self.assertNotIn("authenticated", session)

    def test_csrf_and_wrong_origin_are_rejected(self):
        self.assertEqual(400, self.client.post("/setup", base_url="https://example.com", data={"setup_token": self.env["PASSKEY_SETUP_TOKEN"]}).status_code)
        self.assertEqual(400, self.post("/setup", headers={"Origin": "https://other.example.com"}).status_code)

    def test_invalid_rp_origin_and_session_settings_fail(self):
        for config in [{"WEBAUTHN_RP_ID": "https://example.com"}, {"WEBAUTHN_RP_ID": "example.com/path"},
                       {"WEBAUTHN_ORIGIN": "https://example.com/timetable/"}, {"WEBAUTHN_ORIGIN": "http://example.com"},
                       {"WEBAUTHN_ORIGIN": "https://other.example.com"}, {"TIMETABLE_SESSION_HOURS": "nan"},
                       {"TIMETABLE_SESSION_HOURS": "0"}, {"TIMETABLE_SESSION_COOKIE_PATH": "relative"}]:
            with self.subTest(config=config), self.assertRaises(RuntimeError):
                self.make_app(config)

    def test_subpath_urls_and_cookie_path(self):
        app = self.make_app({"TIMETABLE_SESSION_COOKIE_PATH": "/timetable/"})
        client = app.test_client()
        kwargs = {"base_url": "https://example.com", "environ_overrides": {"SCRIPT_NAME": "/timetable"}}
        self.assertEqual("/timetable/login", client.get("/", **kwargs).location)
        response = client.get("/login", **kwargs)
        self.assertIn('data-options-url="/timetable/auth/login/options"', response.get_data(as_text=True))
        self.assertIn("Path=/timetable/", response.headers["Set-Cookie"])
        self.assertEqual("no-store", response.headers["Cache-Control"])

    def test_os_environment_overrides_dotenv(self):
        from dotenv import load_dotenv
        env_file = Path(self.directory.name) / ".env"
        env_file.write_text("TIMETABLE_AUTH_ENABLED=1\n", encoding="utf-8")
        with patch.dict(os.environ, {"TIMETABLE_AUTH_ENABLED": "0"}, clear=True), patch(
                "app.load_dotenv", side_effect=lambda path, **kwargs: load_dotenv(env_file, **kwargs)):
            app = create_app()
        self.assertFalse(app.config["AUTH_ENABLED"])

    def test_requests_do_not_refresh_authenticated_session(self):
        issued = time.time() - 3600
        with self.client.session_transaction(base_url="https://example.com") as session:
            session.update(authenticated=True, authenticated_at=issued, csrf_token="existing-csrf")
            session.permanent = True
        for _ in range(2):
            self.assertNotIn("Set-Cookie", self.get("/").headers)
        with self.client.session_transaction(base_url="https://example.com") as session:
            self.assertEqual(issued, session["authenticated_at"])

    def test_short_setup_token_fails(self):
        with self.assertRaisesRegex(RuntimeError, "PASSKEY_SETUP_TOKEN"):
            self.make_app({"PASSKEY_SETUP_TOKEN": "change-me"})

    def test_wrong_user_handle_rejects_login(self):
        credential = self.start_login()
        credential["response"]["userHandle"] = bytes_to_base64url(b"another-owner")
        with patch("auth.verify_authentication_response") as verify:
            self.assertEqual(400, self.post("/auth/login/verify", json=credential).status_code)
        verify.assert_not_called()
        self.assert_consumed()

    def test_form_referrer_policy_keeps_same_origin_for_post(self):
        self.assertEqual("same-origin", self.get("/setup").headers["Referrer-Policy"])

    def test_windows_bom_dotenv_auth_off_starts_without_secrets(self):
        from dotenv import load_dotenv
        env_file = Path(self.directory.name) / ".env"
        env_file.write_text("TIMETABLE_AUTH_ENABLED=0\n", encoding="utf-8-sig")
        with patch.dict(os.environ, {}, clear=True), patch(
                "app.load_dotenv", side_effect=lambda path, **kwargs: load_dotenv(env_file, **kwargs)):
            app = create_app()
        self.assertEqual(200, app.test_client().get("/").status_code)


if __name__ == "__main__":
    unittest.main()
