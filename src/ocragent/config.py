import importlib.resources
import os
import tomllib
import string
from pathlib import Path
from typing import Any, Mapping, TypedDict

from dotenv import load_dotenv

_DEFAULT_SETTINGS_TOML = "ocragent.settings.default.toml"
OCRAGENT_CHAT_ENV_NAMES = (
    "OCRAGENT_CHAT_BASE",
    "OCRAGENT_CHAT_AUTHKEY",
    "OCRAGENT_CHAT_MODEL",
)
OCRAGENT_CHAT_ENV_REMINDER = (
    "OCRAGENT_CHAT_* needs to be configured by the user; "
    "otherwise OCRAgent may not work correctly."
)


def read_package_text(filename: str) -> str:
    resource = importlib.resources.files("ocragent") / filename
    return resource.read_text(encoding="utf-8")


def read_package_toml(filename: str) -> dict[str, Any]:
    return tomllib.loads(read_package_text(filename))


def _deep_merge(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(left)
    for key, value in right.items():
        if (
            key in merged
            and isinstance(merged[key], Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    base = os.getenv(OCRAGENT_CHAT_ENV_NAMES[0])
    authkey = os.getenv(OCRAGENT_CHAT_ENV_NAMES[1]) or os.getenv("OPENAI_API_KEY")
    model = os.getenv(OCRAGENT_CHAT_ENV_NAMES[2])
    if base or authkey or model:
        overrides = _deep_merge(
            overrides,
            {
                "aigc": {
                    "api": {
                        "chatcomp": {
                            **({"base": base} if base else {}),
                            **({"authkey": authkey} if authkey else {}),
                            **({"model": model} if model else {}),
                        }
                    }
                }
            },
        )

    host = os.getenv("OCRAGENT_HOST")
    port = os.getenv("OCRAGENT_PORT")
    if host or port:
        web_overrides: dict[str, Any] = {"web": {}}
        if host:
            web_overrides["web"]["host"] = host
        if port:
            web_overrides["web"]["port"] = int(port)
        overrides = _deep_merge(overrides, web_overrides)

    cli_timeout = os.getenv("OCRAGENT_CLI_TIMEOUT")
    if cli_timeout:
        overrides = _deep_merge(overrides, {"cli": {"timeout": int(cli_timeout)}})

    return overrides


def has_ocragent_chat_env() -> bool:
    return any(os.getenv(name) for name in OCRAGENT_CHAT_ENV_NAMES)


def load_ocra_config(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    argv_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    load_dotenv((cwd or Path.cwd()) / ".env", override=False)
    base = read_package_toml(_DEFAULT_SETTINGS_TOML)
    home_cfg = _read_toml_file((home or Path.home()) / ".ocragent" / "ocragent.settings.toml")
    local_cfg = _read_toml_file((cwd or Path.cwd()) / "ocragent.settings.toml")

    merged = _deep_merge(base, home_cfg)
    merged = _deep_merge(merged, local_cfg)

    if argv_overrides is not None:
        if _env_overrides():
            raise RuntimeError("config override source must be either env vars or argv, not both")
        merged = _deep_merge(merged, argv_overrides)
        return merged

    return _deep_merge(merged, _env_overrides())


def _coerce_web_setting(ocra_cfg: Mapping[str, Any], key: str) -> Any:
    web = ocra_cfg.get("web")
    if isinstance(web, Mapping):
        return web.get(key)
    return None


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def get_init_ignore_config(ocra_cfg: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    ignore = _as_mapping(_as_mapping(ocra_cfg.get("init")).get("ignore"))
    ignore_ext = {str(item).lstrip(".").lower() for item in (ignore.get("ext") or [])}
    ignore_folder = {str(item) for item in (ignore.get("folder") or [])}
    return ignore_ext, ignore_folder


class ChatSettings(TypedDict):
    base_url: str
    api_key: str | None
    model: str | None


ocra_config = load_ocra_config()

_host = _coerce_web_setting(ocra_config, "host")
if not isinstance(_host, str) or not _host.strip():
    raise RuntimeError("web.host must be configured in ocragent.settings.default.toml")
OCRAGENT_HOST = _host.strip()

_port = _coerce_web_setting(ocra_config, "port")
if not isinstance(_port, int):
    raise RuntimeError("web.port must be configured in ocragent.settings.default.toml")
OCRAGENT_PORT = int(_port)


def read_prompt_catalog() -> dict:
    return read_package_toml("ocragent.prompt.toml")


def get_prompt_text(name: str) -> str:
    catalog = read_prompt_catalog()
    value = catalog.get(name)
    if not isinstance(value, str) or not value.strip():
        raise KeyError(f"prompt {name!r} not found in ocragent.prompt.toml")
    return value.strip()


def get_user_toolbox_example_text() -> str:
    return read_package_text("ocragent.toolbox_user.example.txt")


def get_user_toolbox_text_path(*, cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / "ocragent.toolbox_user.txt"


def get_user_toolbox_path(*, home: Path | None = None) -> Path:
    return (home or Path.home()) / ".ocragent" / "user_toolbox.py"


def ensure_user_state_dir(*, home: Path | None = None) -> Path:
    state_dir = (home or Path.home()) / ".ocragent"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_chat_settings() -> ChatSettings:
    aigc = ocra_config.get("aigc")
    if not isinstance(aigc, Mapping):
        raise RuntimeError("missing [aigc] config")
    api = aigc.get("api")
    if not isinstance(api, Mapping):
        raise RuntimeError("missing [aigc.api] config")
    chat = api.get("chatcomp")
    if not isinstance(chat, Mapping):
        raise RuntimeError("missing [aigc.api.chatcomp] config")

    base_url = str(chat.get("base") or "").strip()
    if not base_url:
        raise RuntimeError("aigc.api.chatcomp.base is required")

    authkey = chat.get("authkey")
    api_key = str(authkey).strip() if authkey is not None else ""
    if not api_key:
        api_key = None

    model_value = chat.get("model")
    model = str(model_value).strip() if model_value is not None else ""
    if not model:
        model = None

    return {"base_url": base_url, "api_key": api_key, "model": model}


def inject_prompt_context(template: str, context: Mapping[str, str]) -> str:
    return string.Template(template).safe_substitute(context)
