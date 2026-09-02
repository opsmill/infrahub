from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from infrahub.config import GitSettings, Settings, TLSSettings, load

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
CA_BUNDLE = str(TEST_DATA_DIR / "ca-bundle.pem")
OTHER_BUNDLE = str(TEST_DATA_DIR / "ca-bundle-4096.pem")


class TestTLSSettings:
    def test_unset_by_default(self) -> None:
        assert TLSSettings().ca_bundle is None

    def test_existing_pem_file_is_accepted(self) -> None:
        assert TLSSettings(ca_bundle=CA_BUNDLE).ca_bundle == CA_BUNDLE

    def test_missing_file_is_rejected_at_load(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match=r"tls.ca_bundle must be the path to an existing file"):
            TLSSettings(ca_bundle=str(tmp_path / "missing.pem"))

    def test_pem_content_is_rejected(self) -> None:
        # Unlike the per-component HTTP and LDAP settings the global bundle feeds git, boto3 and the
        # database driver, which only take a path, so inline PEM content is not accepted.
        pem_content = Path(CA_BUNDLE).read_text(encoding="utf-8")
        with pytest.raises(ValidationError, match="must be the path to an existing file"):
            TLSSettings(ca_bundle=pem_content)

    def test_file_that_is_not_a_certificate_is_rejected(self, tmp_path: Path) -> None:
        bad_bundle = tmp_path / "bad.pem"
        bad_bundle.write_text("not a certificate", encoding="utf-8")
        with pytest.raises(ValidationError, match=r"Unable to load CA bundle for tls.ca_bundle"):
            TLSSettings(ca_bundle=str(bad_bundle))


class TestGitTLSSettings:
    def test_defaults_verify_with_the_system_store(self) -> None:
        settings = GitSettings()
        assert settings.tls_insecure is False
        assert settings.tls_ca_file is None

    def test_ca_file_is_accepted(self) -> None:
        assert GitSettings(tls_ca_file=CA_BUNDLE).tls_ca_file == CA_BUNDLE

    def test_missing_ca_file_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match=r"git.tls_ca_file must be the path to an existing file"):
            GitSettings(tls_ca_file=str(tmp_path / "missing.pem"))

    def test_insecure_and_ca_file_cannot_be_combined(self) -> None:
        with pytest.raises(ValidationError, match=r"git.tls_insecure cannot be combined with git.tls_ca_file"):
            GitSettings(tls_insecure=True, tls_ca_file=CA_BUNDLE)


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
                "database": {"tls_ca_file": "/etc/infrahub/neo4j-ca.pem"},
                "storage": {"s3": {"INFRAHUB_STORAGE_TLS_CA_FILE": "/etc/infrahub/s3-ca.pem"}},
            }
        )

        assert settings.git.tls_ca_file == OTHER_BUNDLE
        assert settings.http.tls_ca_bundle == OTHER_BUNDLE
        assert settings.database.tls_ca_file == "/etc/infrahub/neo4j-ca.pem"
        assert settings.storage.s3.tls_ca_file == "/etc/infrahub/s3-ca.pem"
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
