from pathlib import Path

import yaml


ROOT=Path(__file__).resolve().parents[1]


def test_compose_data_volume_and_prebuilt_match():
    original=yaml.safe_load((ROOT/"compose.yaml").read_text())
    prebuilt=yaml.safe_load((ROOT/"compose.prebuilt.yaml").read_text())
    service=original["services"]["kilowatch"]
    prebuilt_service=prebuilt["services"]["kilowatch"]
    assert service.pop("build")=="."
    assert service.pop("image")=="kilowatch:local"
    assert prebuilt_service.pop("image")=="ghcr.io/aemjay/kilowatch:${KILOWATCH_VERSION:-1}"
    assert service==prebuilt_service
    assert original["volumes"]==prebuilt["volumes"]
    assert service["read_only"] is True


def test_compose_runs_on_synology_kernel_and_dsm_log_view():
    for name in ["compose.yaml", "compose.prebuilt.yaml", "compose.signal.yaml", "compose.mqtt.yaml"]:
        for service in yaml.safe_load((ROOT/name).read_text())["services"].values():
            assert "cpus" not in service, name
            assert "logging" not in service, name


def test_example_configuration_is_not_live_secret():
    text=(ROOT/".env.example").read_text()
    assert "APP_PASSWORD=" not in text
    assert "BRIDGE_PASSWORD=" not in text
    assert "BRIDGE_HOST=" not in text
    assert "NAS_LAN_IP" not in text
    assert not (ROOT/".env").exists()


def test_no_cdn_or_remote_assets():
    html=(ROOT/"app/static/index.html").read_text(encoding="utf-8")
    js=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
    assert "https://" not in html
    assert "https://" not in js


def test_runtime_and_optional_broker_files_are_complete():
    for name in ["Dockerfile", "docker-entrypoint.sh", "requirements.txt", "app/main.py", "app/static/index.html",
                 "app/static/app.js", "app/static/style.css", "mosquitto/mosquitto.conf", "mosquitto/acl"]:
        assert (ROOT/name).is_file(), name


def test_optional_signal_has_private_service_and_no_published_gateway_port():
    config=yaml.safe_load((ROOT/"compose.signal.yaml").read_text())
    service=config["services"]["signal-api"]
    assert "ports" not in service
    assert service["environment"]["MODE"]=="json-rpc"
    assert "kilowatch-signal:/home/.local/share/signal-cli" in service["volumes"]


def test_platform_is_only_chosen_during_setup():
    for name in ["compose.yaml","compose.prebuilt.yaml","compose.mqtt.yaml","compose.signal.yaml"]:
        for service in yaml.safe_load((ROOT/name).read_text())["services"].values():
            assert service.get("platform") in (None,"${KILOWATCH_PLATFORM:-}"), name


def test_setup_writes_selected_platform():
    import importlib.util
    spec=importlib.util.spec_from_file_location("setup_tool",ROOT/"tools/setup.py")
    tool=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    example=(ROOT/".env.example").read_text()
    assert "KILOWATCH_PLATFORM=\n" in tool.render(example,8088,"auto")
    assert "KILOWATCH_PLATFORM=linux/arm64\n" in tool.render(example,8088,"arm64")
    assert "HTTP_PORT=9000" in tool.render(example,9000,"amd64")
    owned=tool.render(example,8088,"auto","1026","100")
    assert "PUID=1026\n" in owned and "PGID=100\n" in owned


def test_setup_creates_data_folder(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location("setup_tool",ROOT/"tools/setup.py")
    tool=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.prepare_data(tmp_path,"","").is_dir()


def test_data_in_project_folder_and_secrets_in_separate_volume():
    for name in ["compose.yaml","compose.prebuilt.yaml"]:
        config=yaml.safe_load((ROOT/name).read_text())
        service=config["services"]["kilowatch"]
        assert "./data:/data" in service["volumes"]
        assert "kilowatch-secrets:/secrets" in service["volumes"]
        assert "kilowatch-secrets" in config["volumes"]
        assert set(service["cap_add"])=={"CHOWN","DAC_OVERRIDE","FOWNER","SETUID","SETGID"}
    dockerfile=(ROOT/"Dockerfile").read_text()
    assert "ENTRYPOINT" in dockerfile and "SECRETS_DIR=/secrets" in dockerfile
    entrypoint=(ROOT/"docker-entrypoint.sh").read_text()
    assert "setpriv" in entrypoint and "--inh-caps=-all" in entrypoint


def test_version_is_maintained_only_in_the_app_package():
    import app
    assert app.__version__.count(".")==2
    for name in ["Dockerfile","compose.yaml","compose.prebuilt.yaml","package.json",".github/workflows/nas-image.yml"]:
        assert app.__version__ not in (ROOT/name).read_text(), name
