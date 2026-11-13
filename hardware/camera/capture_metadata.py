"""Save metadata from the same completed request as a captured JPEG."""

import json
import math
import os
from pathlib import Path
import tempfile


SETTING_KEYS = (
    "ExposureTime", "AnalogueGain", "DigitalGain", "ColourGains",
    "LensPosition", "AfState", "AeLocked", "AwbLocked",
    "ColourTemperature", "SensorTimestamp", "FrameDuration", "ScalerCrop",
    "SensorTemperature",
)


def json_value(value):
    """Handle libcamera/NumPy values without claiming unavailable values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if hasattr(value, "tolist"):
        return json_value(value.tolist())
    if hasattr(value, "item"):
        return json_value(value.item())
    # Preserve unsupported libcamera structures as text, rather than dropping them.
    return str(value)


def save_request_metadata(image_path, metadata, *, captured_at, capture_size,
                          camera_properties, software_versions, fixed_settings=None,
                          position_guide=None):
    """Atomically write a JSON sidecar; failures propagate to the caller."""
    destination = Path(image_path).with_suffix(".json")
    if destination.exists():
        raise FileExistsError(destination)
    record = {
        "schema_version": 2,
        "image_filename": Path(image_path).name,
        "captured_at": captured_at,
        "captured_at_note": "Host local time near capture; not sensor exposure time",
        "mode": fixed_settings['mode'] if fixed_settings else "metadata_only_original_auto_controls",
        "fixed_settings_verified": bool(fixed_settings and fixed_settings.get('fixed_settings_verified')),
        "fixed_settings": fixed_settings,
        "position_guide": position_guide,
        "capture_size": list(capture_size),
        "stream_format": "RGB888",
        "settings": {key: metadata.get(key) for key in SETTING_KEYS},
        "missing_settings": [key for key in SETTING_KEYS if key not in metadata],
        "metadata": metadata,
        "camera_properties": camera_properties,
        "software_versions": software_versions,
        "units": {"ExposureTime": "microseconds", "FrameDuration": "microseconds",
                  "SensorTimestamp": "nanoseconds; sensor clock, not wall clock"},
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=destination.parent, delete=False) as out:
            temporary = Path(out.name)
            json.dump(json_value(record), out, ensure_ascii=False, indent=2,
                      allow_nan=False)
            out.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return destination
