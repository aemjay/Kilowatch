from pathlib import Path
import re

import yaml


ROOT=Path(__file__).resolve().parents[1]


def test_compose_data_volume_and_prebuilt_match():
    original=yaml.safe_load((ROOT/"compose.build.yaml").read_text())
    prebuilt=yaml.safe_load((ROOT/"compose.yaml").read_text())
    service=original["services"]["kilowatch"]
    prebuilt_service=prebuilt["services"]["kilowatch"]
    assert service.pop("build")=="."
    assert service.pop("image")=="kilowatch:local"
    assert prebuilt_service.pop("image")=="ghcr.io/aemjay/kilowatch:${KILOWATCH_VERSION:-1}"
    assert service==prebuilt_service
    assert original["volumes"]==prebuilt["volumes"]
    assert service["read_only"] is True


def test_compose_runs_on_synology_kernel_and_dsm_log_view():
    for name in ["compose.build.yaml", "compose.yaml", "compose.signal.yaml", "compose.mqtt.yaml"]:
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
    for name in ["compose.build.yaml","compose.yaml","compose.mqtt.yaml","compose.signal.yaml"]:
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
    for name in ["compose.build.yaml","compose.yaml"]:
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
    for name in ["Dockerfile","compose.build.yaml","compose.yaml","package.json",".github/workflows/nas-image.yml"]:
        assert app.__version__ not in (ROOT/name).read_text(), name


def test_containers_have_stable_names_and_default_file_is_prebuilt():
    names={"compose.yaml":"kilowatch","compose.build.yaml":"kilowatch","compose.signal.yaml":"kilowatch-signal","compose.mqtt.yaml":"kilowatch-mqtt"}
    for file,name in names.items():
        service=next(iter(yaml.safe_load((ROOT/file).read_text())["services"].values()))
        assert service["container_name"]==name, file
    # Der Container Manager speichert die gewählte Datei als compose.yaml: Standard ist das fertige Image.
    assert "build" not in yaml.safe_load((ROOT/"compose.yaml").read_text())["services"]["kilowatch"]


def test_user_is_detected_automatically_unless_set():
    for name in ["compose.yaml","compose.build.yaml"]:
        environment=yaml.safe_load((ROOT/name).read_text())["services"]["kilowatch"]["environment"]
        assert environment["PUID"]=="${PUID:-}" and environment["PGID"]=="${PGID:-}"
    entrypoint=(ROOT/"docker-entrypoint.sh").read_text()
    assert "stat -c %u" in entrypoint and "SCHNELLSTART" in entrypoint
    assert (ROOT/"tools/install.sh").is_file() and (ROOT/"docs/SCHNELLSTART.md").is_file()


def test_stylesheet_has_light_dark_and_print_themes_and_no_stray_colors():
    css=(ROOT/"app/static/style.css").read_text()
    assert "@media (prefers-color-scheme:dark){:root:not([data-theme=light])" in css
    assert ":root[data-theme=dark]{color-scheme:dark" in css and "@media print{:root,:root[data-theme=dark]{color-scheme:light" in css
    # Außerhalb der Themenblöcke nur Variablen; feste Farben nur in den immer dunklen bzw. hellen Bereichen.
    body=css.split("\n",5)[5]
    for selector,declarations in re.findall(r"([^{}]+)\{([^{}]*)\}",body):
        if re.search(r"sidebar|nav|brand|home-|login-art|login-copy|login-foot|highlight",selector):
            continue
        for prop,value in re.findall(r"([\w-]+):([^;]+)",declarations):
            if prop in ("color","background","background-color","border","border-color","fill","stroke"):
                assert not re.search(r"#[0-9a-fA-F]{3,8}\b",value),(selector,prop,value)


def test_signal_colours_exist_in_every_theme_and_stay_visible_in_dark_mode():
    css=(ROOT/"app/static/style.css").read_text()
    blocks=[css.split(":root{color-scheme:light",1)[1].split("}",1)[0],
            css.split(":root:not([data-theme=light]){",1)[1].split("}",1)[0],
            css.split(":root[data-theme=dark]{",1)[1].split("}",1)[0],
            css.split("@media print{:root,:root[data-theme=dark]{",1)[1].split("}",1)[0]]
    for block in blocks:
        for name in ("signal-ok","signal-warn","signal-error","signal-blue","signal-quality"):
            assert f"--{name}:#" in block, name
    # Statuspunkt und Hinweise nutzen Signalfarben, keine in Dunkel abgedunkelten Flächenfarben.
    assert ".status-dot,.main-footer i{display:inline-block;width:6px;height:6px;background:var(--signal-ok)" in css
    assert "--signal-ok:#414843" not in css


def test_light_mode_text_colours_reach_aa_contrast_on_the_page_background():
    css=(ROOT/"app/static/style.css").read_text()
    light=css.split(":root{color-scheme:light",1)[1].split("}",1)[0]
    colours=dict(re.findall(r"--([\w-]+):(#[0-9a-fA-F]{6})",light))
    def lum(h):
        r,g,b=(int(h[i:i+2],16)/255 for i in (1,3,5))
        f=lambda x:x/12.92 if x<=.03928 else ((x+.055)/1.055)**2.4
        return .2126*f(r)+.7152*f(g)+.0722*f(b)
    ratio=lambda a,b:(max(lum(a),lum(b))+.05)/(min(lum(a),lum(b))+.05)
    paper=colours["paper"]
    # Dunkle Schriftfarben (auf hellen Flächen) mindestens 4,5:1; ausgenommen rein dekorative Zeichen
    # und die Versionsnummer, die auf der immer dunklen Seitenleiste steht.
    decorative={"k-text-a7b795","k-text-b2b9ae","k-text-657d83"}
    for name,value in colours.items():
        if (name.startswith("k-text-") or name=="muted") and name not in decorative and lum(value)<0.6:
            assert ratio(value,paper)>=4.5,(name,value)
    assert ratio(colours["chart-line"],"#ffffff")>=3
