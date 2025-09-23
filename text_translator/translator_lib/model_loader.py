import json
import os
from typing import Dict, Any, Optional
import copy

class ModelConfigError(Exception):
    """Custom exception for model configuration loading and parsing errors.

    This exception is raised when the `load_model_configs` function encounters
    a problem, such as a missing file, invalid JSON, or a broken inheritance
    chain in the configuration.
    """
    pass

def _deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges a source dictionary into a destination dictionary.

    This function is a key part of handling configuration inheritance. It merges
    the `source` dictionary into the `destination` dictionary. If a key exists
    in both and both values are dictionaries, it recursively merges them.
    Otherwise, the value from the `source` overwrites the `destination`'s value.

    Args:
        source: The dictionary containing new or overriding data. Its values
                take precedence.
        destination: The base dictionary that will be modified.

    Returns:
        The `destination` dictionary, modified in place with the merged data.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            destination[key] = _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination

def load_model_configs(config_path: str) -> Dict[str, Any]:
    """Loads, processes, and resolves inheritance for model configs from a JSON file.

    This function is responsible for reading a `models.json` file that defines
    multiple model configurations. It supports an "inherits" mechanism, where a
    model configuration can specify a parent configuration. When inheritance
    is used, the parent's configuration is deep-merged into the child's, with
    the child's specific settings overriding the parent's.

    This allows for creating a base configuration and then defining several
    variations without repeating common settings.

    Args:
        config_path: The absolute or relative path to the `models.json` file.

    Returns:
        A dictionary where each key is a model name and the value is its fully
        resolved configuration dictionary (i.e., after inheritance has been
        applied).

    Raises:
        ModelConfigError: If the configuration file cannot be found, contains
                          invalid JSON, or if a model specifies a non-existent
                          parent in the `inherits` field.
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
    """Retrieves a specific model's config, falling back to a default if needed.

    This function safely retrieves a configuration for a given `model_name` from
    the dictionary of all loaded configurations. If the specified `model_name`
    is not found, it attempts to return a default configuration identified by
    `default_config_key`.

    It also ensures that the returned configuration dictionary has a `params`
    key, adding an empty one if it's missing. This prevents errors in downstream
    code that expects this key to be present.

    Args:
        model_name: The name of the model whose configuration is requested.
        all_configs: A dictionary containing all resolved model configurations,
                     as returned by `load_model_configs`.
        default_config_key: The key in `all_configs` that corresponds to the
                            default configuration.

    Returns:
        The configuration dictionary for the requested model.

    Raises:
        ModelConfigError: If the `model_name` is not found in `all_configs` and
                          no default configuration is available either.
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
