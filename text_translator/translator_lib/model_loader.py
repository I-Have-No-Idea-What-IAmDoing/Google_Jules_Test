import json
import os
from typing import Dict, Any, Set
import copy

class ModelConfigError(Exception):
    """Custom exception for model configuration loading and parsing errors."""
    pass

def _deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merges a source dictionary into a destination dictionary.
    The destination is modified in place.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination

def _resolve_config(
    name: str,
    configs: Dict[str, Any],
    resolved_configs: Dict[str, Any],
    resolving_stack: Set[str]
) -> Dict[str, Any]:
    """
    Recursively resolves a single model's configuration, handling inheritance.
    """
    # Detect circular dependencies
    if name in resolving_stack:
        raise ModelConfigError(f"Circular inheritance detected for model '{name}'. Chain: {' -> '.join(resolving_stack)} -> {name}")

    # If already resolved, return the cached version
    if name in resolved_configs:
        return resolved_configs[name]

    if name not in configs:
        raise ModelConfigError(f"Model '{name}' not found in configuration files.")

    resolving_stack.add(name)

    # Make a deep copy to avoid modifying the original config dict
    config = copy.deepcopy(configs[name])

    parent_name = config.pop("inherits", None)
    if parent_name:
        # Recursively resolve the parent config first
        parent_config = _resolve_config(parent_name, configs, resolved_configs, resolving_stack)

        # The child's config is merged into the parent's. Child's values take precedence.
        # We merge the child `config` into a copy of the `parent_config`.
        resolved_config = _deep_merge(config, copy.deepcopy(parent_config))
    else:
        resolved_config = config

    # Clean up the stack for the current resolution path
    resolving_stack.remove(name)

    # Cache the fully resolved config
    resolved_configs[name] = resolved_config

    return resolved_config

def load_model_configs(config_path: str) -> Dict[str, Any]:
    """
    Loads, processes, and resolves inheritance for model configs from a JSON file.
    Supports chained and multiple inheritance.
    """
    if not os.path.exists(config_path):
        raise ModelConfigError(f"Model configuration file not found at: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            configs = json.load(f)
    except json.JSONDecodeError as e:
        raise ModelConfigError(f"Error decoding JSON from {config_path}: {e}")

    resolved_configs: Dict[str, Any] = {}
    for name in configs:
        if name not in resolved_configs:
            _resolve_config(name, configs, resolved_configs, set())

    return resolved_configs

def get_model_config(
    model_name: str,
    all_configs: Dict[str, Any],
    default_config_key: str = "_default"
) -> Dict[str, Any]:
    """
    Retrieves a specific model's config, falling back to a default if needed.
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

    return copy.deepcopy(config)
