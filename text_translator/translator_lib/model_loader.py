import json
import os
from typing import Dict, Any, Optional
import copy

class ModelConfigError(Exception):
    """Custom exception raised for errors in loading or parsing model configs."""
    pass

def _deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges a source dictionary into a destination dictionary.

    This is used to handle config inheritance, where a child config's values
    overwrite the parent's values. Nested dictionaries are merged recursively.

    Args:
        source: The dictionary with higher priority data.
        destination: The dictionary to be merged into.

    Returns:
        The `destination` dictionary, modified in place.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            destination[key] = _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination

def load_model_configs(config_path: str) -> Dict[str, Any]:
    """Loads and processes model configurations from a JSON file.

    This function reads a `models.json` file, which can define multiple model
    configurations. It also handles an `inherits` key, allowing one model config
    to extend another. It merges the parent's configuration into the child's,
    with the child's properties taking precedence.

    Args:
        config_path: The file path to the `models.json` configuration file.

    Returns:
        A dictionary where keys are model names and values are their fully
        resolved configuration dictionaries.

    Raises:
        ModelConfigError: If the file cannot be found, is not valid JSON, or
                          if an `inherits` key points to a non-existent model.
    """
    if not os.path.exists(config_path):
        raise ModelConfigError(f"Model configuration file not found at: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            configs = json.load(f)
        except json.JSONDecodeError as e:
            raise ModelConfigError(f"Error decoding JSON from {config_path}: {e}")

    # Resolve inheritance
    resolved_configs: Dict[str, Any] = {}
    for name, config in configs.items():
        if name in resolved_configs:
            continue # Already resolved as a parent

        # Start with a deep copy of the config to avoid modifying the original
        current_config = copy.deepcopy(config)

        parent_name = current_config.pop("inherits", None)
        if parent_name:
            if parent_name not in configs:
                raise ModelConfigError(f"Model '{name}' inherits from non-existent model '{parent_name}'.")

            # Deep copy the parent to avoid modifying it
            parent_config = copy.deepcopy(configs[parent_name])

            # Merge the parent config into the current config.
            # The current config's values take precedence.
            resolved_config = _deep_merge(current_config, parent_config)
        else:
            resolved_config = current_config

        resolved_configs[name] = resolved_config

    return resolved_configs


def get_model_config(
    model_name: str,
    all_configs: Dict[str, Any],
    default_config_key: str = "_default"
) -> Dict[str, Any]:
    """Retrieves a specific model's config, with a fallback to the default.

    This function safely accesses the dictionary of all configurations. If the
    requested `model_name` exists, its configuration is returned. If not, it
    looks for a default configuration specified by `default_config_key`. It also
    ensures that the returned config dictionary contains a 'params' key.

    Args:
        model_name: The name of the desired model configuration.
        all_configs: The dictionary of all available model configurations,
                     typically loaded by `load_model_configs`.
        default_config_key: The key used to identify the default configuration
                            to use as a fallback.

    Returns:
        The final configuration dictionary for the requested model.

    Raises:
        ModelConfigError: If the requested `model_name` is not found and no
                          default configuration is available.
    """
    if model_name in all_configs:
        config = all_configs[model_name]
    elif default_config_key in all_configs:
        config = all_configs[default_config_key]
    else:
        raise ModelConfigError(
            f"Model '{model_name}' not found in configuration, and no default ('{default_config_key}') is defined."
        )

    # Ensure the config has the expected structure
    if "params" not in config:
        config["params"] = {}

    return config
