from __future__ import annotations

import ssl
from pathlib import Path

import pytest
from pydantic import ValidationError

from infrahub.config import GitSettings, S3StorageSettings, Settings, TLSSettings, load

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
CA_BUNDLE = str(TEST_DATA_DIR / "ca-bundle.pem")
OTHER_BUNDLE = str(TEST_DATA_DIR / "ca-bundle-4096.pem")


@pytest.fixture
def materialized_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect materialized PEM bundles into the test's temporary directory."""
    directory = tmp_path / "infrahub-tls"
    monkeypatch.setattr("infrahub.tls.bundle.MATERIALIZED_BUNDLE_DIRECTORY", directory)
    return directory


class TestTLSSettings:
    def test_unset_by_default(self) -> None:
        assert TLSSettings().ca_bundle is None

    def test_existing_pem_file_is_accepted(self) -> None:
        assert TLSSettings(ca_bundle=CA_BUNDLE).ca_bundle == CA_BUNDLE

    def test_missing_file_is_rejected_at_load(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match=r"tls.ca_bundle: must be the path to an existing file or PEM text"):
            TLSSettings(ca_bundle=str(tmp_path / "missing.pem"))

    def test_pem_text_is_written_to_a_file(self, materialized_directory: Path) -> None:
        # git, boto3, the Neo4j driver and redis-py only take a path, so inline PEM text is written to a
        # file named after its content and the setting holds that path once loaded.
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")

        settings = TLSSettings.model_validate({"ca_bundle": pem_content})

        materialized = Path(settings.ca_bundle or "")
        assert materialized.parent == materialized_directory
        assert materialized.name.startswith("ca-bundle-")
        assert materialized.suffix == ".pem"
        assert materialized.read_text(encoding="utf-8") == pem_content.strip() + "\n"

    def test_pem_text_with_escaped_newlines_is_accepted(self, materialized_directory: Path) -> None:
        # Environment files cannot always carry real line breaks.
        escaped = Path(CA_BUNDLE).read_text(encoding="utf-8").strip().replace("\n", "\\n")

        settings = TLSSettings.model_validate({"ca_bundle": escaped})

        assert (
            Path(settings.ca_bundle or "").read_text(encoding="utf-8")
            == Path(CA_BUNDLE).read_text(encoding="utf-8").strip() + "\n"
        )

    def test_pem_text_that_is_not_a_certificate_is_rejected(self, materialized_directory: Path) -> None:
        with pytest.raises(ValidationError, match=r"tls.ca_bundle: the value is not a valid PEM certificate bundle"):
            TLSSettings.model_validate({"ca_bundle": "-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----"})
        # Nothing is written before the text has been validated.
        assert not materialized_directory.exists()

    def test_file_that_is_not_a_certificate_is_rejected(self, tmp_path: Path) -> None:
        bad_bundle = tmp_path / "bad.pem"
        bad_bundle.write_text("not a certificate", encoding="utf-8")
        with pytest.raises(ValidationError, match=r"tls.ca_bundle: unable to load the CA bundle"):
            TLSSettings(ca_bundle=str(bad_bundle))

    def test_unreadable_file_is_reported_as_a_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Tests run as root, so chmod cannot make the file unreadable; fail the loader the way the OS would.
        def fake(*args: object, **kwargs: object) -> None:
            raise PermissionError("Permission denied")

        monkeypatch.setattr(ssl, "create_default_context", fake)
        with pytest.raises(ValidationError, match=r"tls.ca_bundle: unable to load the CA bundle"):
            TLSSettings.model_validate({"ca_bundle": CA_BUNDLE})


class TestGitTLSSettings:
    def test_defaults_verify_with_the_system_store(self) -> None:
        settings = GitSettings()
        assert settings.tls_insecure is False
        assert settings.tls_ca_file is None

    def test_ca_file_is_accepted(self) -> None:
        assert GitSettings(tls_ca_file=CA_BUNDLE).tls_ca_file == CA_BUNDLE

    def test_missing_ca_file_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match=r"git.tls_ca_file: must be the path to an existing file or PEM text"):
            GitSettings(tls_ca_file=str(tmp_path / "missing.pem"))

    def test_insecure_wins_over_a_configured_ca_file(self) -> None:
        # Switching verification off temporarily must not require dropping the bundle.
        settings = GitSettings.model_validate({"tls_insecure": True, "tls_ca_file": CA_BUNDLE})

        assert settings.tls_insecure is True
        assert settings.tls_ca_file == CA_BUNDLE

    def test_unreadable_ca_file_is_reported_as_a_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Tests run as root, so chmod cannot make the file unreadable; fail the loader the way the OS would.
        def fake(*args: object, **kwargs: object) -> None:
            raise PermissionError("Permission denied")

        monkeypatch.setattr(ssl, "create_default_context", fake)
        with pytest.raises(ValidationError, match=r"git.tls_ca_file: unable to load the CA bundle"):
            GitSettings.model_validate({"tls_ca_file": CA_BUNDLE})


class TestS3TLSSettings:
    def test_ca_file_is_accepted_on_a_tls_endpoint(self) -> None:
        # Keys are the environment variable names, the way operators set them; use_ssl defaults to true.
        settings = S3StorageSettings.model_validate({"INFRAHUB_STORAGE_TLS_CA_FILE": CA_BUNDLE})

        assert settings.use_ssl is True
        assert settings.tls_ca_file == CA_BUNDLE

    def test_ca_file_on_a_plaintext_endpoint_is_rejected(self) -> None:
        # boto3 never reads verify= on an http:// endpoint, so the setting would give a false sense of security.
        with pytest.raises(
            ValidationError, match=r"storage.s3.tls_ca_file cannot be combined with storage.s3.use_ssl=false"
        ):
            S3StorageSettings.model_validate(
                {"INFRAHUB_STORAGE_TLS_CA_FILE": CA_BUNDLE, "INFRAHUB_STORAGE_USE_SSL": False}
            )


class TestGlobalCaBundleResolution:
    """The global ``tls.ca_bundle`` fills every component that verifies certificates and left its own CA unset."""

    def test_without_global_bundle_components_stay_on_the_system_store(self) -> None:
        settings = Settings.model_validate(
            {"log_forwarding": {"destinations": [{"name": "syslog", "host": "logs.example.com"}]}}
        )

        assert settings.git.tls_ca_file is None
        assert settings.http.tls_ca_bundle is None
        assert settings.database.tls_ca_file is None
        assert settings.broker.tls_ca_file is None
        assert settings.cache.tls_ca_file is None
        assert settings.storage.s3.tls_ca_file is None
        assert settings.ldap.tls_ca_bundle is None
        assert settings.trace.tls_ca_bundle is None
        assert settings.log_forwarding.destinations[0].tls_ca_bundle is None

    def test_global_bundle_fills_every_unset_component(self) -> None:
        settings = Settings.model_validate(
            {
                "tls": {"ca_bundle": CA_BUNDLE},
                "log_forwarding": {"destinations": [{"name": "syslog", "host": "logs.example.com"}]},
            }
        )

        assert settings.git.tls_ca_file == CA_BUNDLE
        assert settings.http.tls_ca_bundle == CA_BUNDLE
        assert settings.database.tls_ca_file == CA_BUNDLE
        assert settings.broker.tls_ca_file == CA_BUNDLE
        assert settings.cache.tls_ca_file == CA_BUNDLE
        assert settings.storage.s3.tls_ca_file == CA_BUNDLE
        assert settings.ldap.tls_ca_bundle == CA_BUNDLE
        assert settings.log_forwarding.destinations[0].tls_ca_bundle == CA_BUNDLE

    def test_component_setting_wins_over_the_global_bundle(self) -> None:
        settings = Settings.model_validate(
            {
                "tls": {"ca_bundle": CA_BUNDLE},
                "git": {"tls_ca_file": OTHER_BUNDLE},
                "http": {"tls_ca_bundle": OTHER_BUNDLE},
                "database": {"tls_ca_file": OTHER_BUNDLE},
                "storage": {"s3": {"INFRAHUB_STORAGE_TLS_CA_FILE": OTHER_BUNDLE}},
            }
        )

        assert settings.git.tls_ca_file == OTHER_BUNDLE
        assert settings.http.tls_ca_bundle == OTHER_BUNDLE
        assert settings.database.tls_ca_file == OTHER_BUNDLE
        assert settings.storage.s3.tls_ca_file == OTHER_BUNDLE
        # Components without their own setting still get the global one.
        assert settings.broker.tls_ca_file == CA_BUNDLE
        assert settings.cache.tls_ca_file == CA_BUNDLE

    def test_insecure_component_is_left_alone(self) -> None:
        # An explicit tls_insecure means "do not verify"; handing that component a CA bundle would either be
        # ignored or, for the HTTP client built with force_verify, silently turn verification back on.
        settings = Settings.model_validate(
            {
                "tls": {"ca_bundle": CA_BUNDLE},
                "git": {"tls_insecure": True},
                "http": {"tls_insecure": True},
                "cache": {"tls_insecure": True},
            }
        )

        assert settings.git.tls_ca_file is None
        assert settings.http.tls_ca_bundle is None
        assert settings.cache.tls_ca_file is None
        assert settings.database.tls_ca_file == CA_BUNDLE

    def test_plaintext_s3_endpoint_is_left_alone(self) -> None:
        # With use_ssl disabled boto3 talks http:// and ignores verify=, so the plaintext endpoint must not
        # inherit the global bundle while the other components still do.
        settings = Settings.model_validate(
            {"tls": {"ca_bundle": CA_BUNDLE}, "storage": {"s3": {"INFRAHUB_STORAGE_USE_SSL": False}}}
        )

        assert settings.storage.s3.tls_ca_file is None
        assert settings.database.tls_ca_file == CA_BUNDLE

    @pytest.mark.parametrize(
        ("trace_settings", "expected"),
        [
            pytest.param({"exporter_type": "otlp", "exporter_protocol": "grpc"}, None, id="grpc-plaintext-default"),
            pytest.param(
                {"exporter_type": "otlp", "exporter_protocol": "grpc", "insecure": False}, CA_BUNDLE, id="grpc-tls"
            ),
            pytest.param(
                {
                    "exporter_type": "otlp",
                    "exporter_protocol": "http/protobuf",
                    "insecure": False,
                    "exporter_endpoint": "https://collector.example.com:4318/v1/traces",
                },
                CA_BUNDLE,
                id="http-protobuf-https",
            ),
            pytest.param(
                {
                    "exporter_type": "otlp",
                    "exporter_protocol": "http/protobuf",
                    "insecure": False,
                    "exporter_endpoint": "http://collector.example.com:4318/v1/traces",
                },
                None,
                id="http-protobuf-plaintext",
            ),
            pytest.param({"exporter_type": "console"}, None, id="console-exporter"),
        ],
    )
    def test_trace_only_gets_the_bundle_on_an_encrypted_exporter(
        self, trace_settings: dict[str, object], expected: str | None
    ) -> None:
        # On grpc a CA bundle switches the exporter from plaintext to TLS, so a plaintext exporter must
        # not inherit the global bundle.
        settings = Settings.model_validate({"tls": {"ca_bundle": CA_BUNDLE}, "trace": trace_settings})

        assert settings.trace.tls_ca_bundle == expected

    def test_resolution_applies_when_loading_from_config_data(self) -> None:
        settings = load(config_data={"tls": {"ca_bundle": CA_BUNDLE}})

        assert settings.git.tls_ca_file == CA_BUNDLE
        assert settings.http.tls_ca_bundle == CA_BUNDLE

    def test_settings_instances_do_not_share_resolved_values(self) -> None:
        # Resolution mutates the section objects; pydantic must hand every Settings its own copies.
        Settings.model_validate({"tls": {"ca_bundle": CA_BUNDLE}})

        assert Settings().http.tls_ca_bundle is None


class TestPemTextAcrossComponents:
    """Every CA setting accepts PEM text and holds the materialized file's path once loaded."""

    @pytest.mark.parametrize(
        ("section", "settings_key", "attribute"),
        [
            pytest.param("git", "tls_ca_file", "tls_ca_file", id="git"),
            pytest.param("http", "tls_ca_bundle", "tls_ca_bundle", id="http"),
            pytest.param("database", "tls_ca_file", "tls_ca_file", id="database"),
            pytest.param("broker", "tls_ca_file", "tls_ca_file", id="broker"),
            pytest.param("cache", "tls_ca_file", "tls_ca_file", id="cache"),
            pytest.param("trace", "tls_ca_bundle", "tls_ca_bundle", id="trace"),
        ],
    )
    def test_component_pem_text_becomes_a_path(
        self, materialized_directory: Path, section: str, settings_key: str, attribute: str
    ) -> None:
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")

        settings = Settings.model_validate({section: {settings_key: pem_content}})

        resolved = Path(getattr(getattr(settings, section), attribute))
        assert resolved.parent == materialized_directory
        assert resolved.read_text(encoding="utf-8") == pem_content.strip() + "\n"

    def test_s3_pem_text_becomes_a_path(self, materialized_directory: Path) -> None:
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")

        settings = Settings.model_validate({"storage": {"s3": {"INFRAHUB_STORAGE_TLS_CA_FILE": pem_content}}})

        assert Path(settings.storage.s3.tls_ca_file or "").parent == materialized_directory

    def test_ldap_pem_text_becomes_a_path_when_tls_is_enabled(self, materialized_directory: Path) -> None:
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")

        settings = Settings.model_validate({"ldap": {"tls_enabled": True, "tls_ca_bundle": pem_content}})

        assert Path(settings.ldap.tls_ca_bundle or "").parent == materialized_directory

    def test_log_forwarding_destination_pem_text_becomes_a_path(self, materialized_directory: Path) -> None:
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")

        settings = Settings.model_validate(
            {
                "log_forwarding": {
                    "destinations": [
                        {
                            "name": "siem",
                            "host": "logs.example.com",
                            "protocol": "tcp",
                            "tls_enabled": True,
                            "tls_ca_bundle": pem_content,
                        }
                    ]
                }
            }
        )

        assert Path(settings.log_forwarding.destinations[0].tls_ca_bundle or "").parent == materialized_directory

    def test_destination_missing_file_is_rejected_at_load(self, tmp_path: Path) -> None:
        with pytest.raises(
            ValidationError, match=r"log_forwarding.destinations\[siem\].tls_ca_bundle: must be the path to an existing"
        ):
            Settings.model_validate(
                {
                    "log_forwarding": {
                        "destinations": [
                            {"name": "siem", "host": "logs.example.com", "tls_ca_bundle": str(tmp_path / "missing.pem")}
                        ]
                    }
                }
            )

    def test_global_pem_text_reaches_every_component_as_the_same_path(self, materialized_directory: Path) -> None:
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")

        settings = Settings.model_validate({"tls": {"ca_bundle": pem_content}})

        materialized = settings.tls.ca_bundle
        assert materialized is not None
        assert Path(materialized).parent == materialized_directory
        assert settings.git.tls_ca_file == materialized
        assert settings.database.tls_ca_file == materialized
        assert settings.broker.tls_ca_file == materialized
        assert settings.cache.tls_ca_file == materialized
        assert settings.storage.s3.tls_ca_file == materialized
        assert settings.http.tls_ca_bundle == materialized
        # One bundle, one file: every section points at the same materialized file.
        assert len(list(materialized_directory.iterdir())) == 1

    @pytest.mark.parametrize("section", ["database", "broker", "cache"])
    def test_component_missing_file_is_rejected_at_load(self, section: str, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match=rf"{section}.tls_ca_file: must be the path to an existing file"):
            Settings.model_validate({section: {"tls_ca_file": str(tmp_path / "missing.pem")}})
