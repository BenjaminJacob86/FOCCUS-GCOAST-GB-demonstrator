"""Load demonstrator settings from a YAML config file.

Select a config with the ``APP_CONFIG`` environment variable, e.g.::

    APP_CONFIG=config/black_sea_douglas.yaml streamlit run app_pmtiles_assessment_two_paged_s3.py

Default: ``config/german_bight.yaml`` (relative to this file's directory).
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "german_bight.yaml"


@dataclass(frozen=True)
class ScenarioConfig:
    """One vegetation / reference scenario (S3 subfolder under each run date)."""

    key: str
    label: str
    subfolder: str
    is_difference: bool = False


@dataclass(frozen=True)
class AppConfig:
    page_title: str
    dashboard_page_title: str
    header_title: str
    tagline: str
    logo_primary: Path
    logo_fallback: Path
    about_markdown: Path
    endpoint_url: str
    s3_bucket: str
    s3_prefix: str
    default_run_date: dt.date
    domain_bounds: tuple[float, float, float, float]
    indicator_layers: dict[str, dict[str, Any]]
    scenarios: tuple[ScenarioConfig, ...]
    default_scenario_key: str | None


_config: AppConfig | None = None
_config_mtime: float | None = None
_config_path_resolved: Path | None = None


def _resolve_config_path(path: str | Path | None = None) -> Path:
    if path is not None:
        candidate = Path(path)
    else:
        env = os.environ.get("APP_CONFIG", "").strip()
        candidate = Path(env) if env else DEFAULT_CONFIG_PATH
    if not candidate.is_absolute():
        candidate = APP_DIR / candidate
    return candidate.resolve()


def _normalize_scenarios(raw: dict[str, Any] | None) -> tuple[tuple[ScenarioConfig, ...], str | None]:
    if not raw:
        return (), None
    default_key = raw.get("default")
    items = raw.get("items") or {}
    scenarios: list[ScenarioConfig] = []
    for key, cfg in items.items():
        if not isinstance(cfg, dict):
            continue
        subfolder = str(cfg.get("subfolder", key)).strip("/")
        scenarios.append(
            ScenarioConfig(
                key=str(key),
                label=str(cfg.get("label", key)),
                subfolder=subfolder,
                is_difference=bool(cfg.get("is_difference", False)),
            )
        )
    if not scenarios:
        return (), None
    default_scenario_key = str(default_key) if default_key else scenarios[0].key
    return tuple(scenarios), default_scenario_key


def _normalize_indicator_layers(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    layers: dict[str, dict[str, Any]] = {}
    for label, cfg in raw.items():
        layer = dict(cfg)
        fallbacks = layer.get("attribute_fallbacks")
        if fallbacks is not None:
            layer["attribute_fallbacks"] = tuple(fallbacks)
        layers[str(label)] = layer
    return layers


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = _resolve_config_path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    app = data.get("app", {})
    s3 = data.get("s3", {})
    domain = data.get("domain", {})
    bounds = domain.get("bounds", [53.04, 5.12, 55.63, 10.40])
    if len(bounds) != 4:
        raise ValueError(f"domain.bounds must have 4 values, got {bounds!r}")

    run_date_raw = str(domain.get("default_run_date", "2026-06-04"))
    default_run_date = dt.date.fromisoformat(run_date_raw)
    scenarios, default_scenario_key = _normalize_scenarios(data.get("scenarios"))

    return AppConfig(
        page_title=str(app.get("page_title", "FOCCUS demonstrator")),
        dashboard_page_title=str(
            app.get("dashboard_page_title", "SCHISM indicators + assessment")
        ),
        header_title=str(app.get("header_title", "FOCCUS Demonstrator")),
        tagline=str(app.get("tagline", "")),
        logo_primary=APP_DIR / str(app.get("logo_primary", "FOCCUS_Logo_clean RGB_whiteBG.png")),
        logo_fallback=APP_DIR / str(app.get("logo_fallback", "FOCCUS_Logo_clean RGB.png")),
        about_markdown=APP_DIR / str(app.get("about_markdown", "ESC1GB.md")),
        endpoint_url=str(s3.get("endpoint_url", "https://minio.dive.edito.eu")),
        s3_bucket=str(s3.get("bucket", "oidc-jacobb")),
        s3_prefix=str(s3.get("prefix", "Hereon/IndicatorAssesment")).strip("/"),
        default_run_date=default_run_date,
        domain_bounds=(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])),
        indicator_layers=_normalize_indicator_layers(data.get("indicators", {})),
        scenarios=scenarios,
        default_scenario_key=default_scenario_key,
    )


def get_config() -> AppConfig:
    """Return config, reloading YAML when the file changes (Streamlit reruns keep modules alive)."""
    global _config, _config_mtime, _config_path_resolved
    path = _resolve_config_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None

    if (
        _config is None
        or _config_path_resolved != path
        or (_config_mtime is not None and mtime is not None and mtime != _config_mtime)
    ):
        _config = load_config(path)
        _config_mtime = mtime
        _config_path_resolved = path
    return _config


def reload_config(path: str | Path | None = None) -> AppConfig:
    """Force reload (useful in tests or after changing ``APP_CONFIG``)."""
    global _config, _config_mtime, _config_path_resolved
    resolved = _resolve_config_path(path)
    _config = load_config(resolved)
    try:
        _config_mtime = resolved.stat().st_mtime
    except OSError:
        _config_mtime = None
    _config_path_resolved = resolved
    return _config
