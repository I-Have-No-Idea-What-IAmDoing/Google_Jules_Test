import json
import os
from typing import Dict, Any, Set
import copy

class ModelConfigError(Exception):
    """Custom exception for model configuration loading and parsing errors."""
    pass

def _deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges a source dictionary into a destination dictionary.

    This function is used to combine model configurations, particularly for
    handling inheritance. It merges the `source` dictionary into the
    `destination` dictionary. If a key exists in both and both values are
    dictionaries, it performs a recursive merge. Otherwise, the value from the
    `source` overwrites the value in the `destination`.

    Note:
        The `destination` dictionary is modified in place.

    Args:
        source: The dictionary to merge from. Its values take precedence.
        destination: The dictionary to merge into. It is modified directly.

    Returns:
        The modified `destination` dictionary.
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
    """Recursively resolves a single model's configuration, handling inheritance.

    This function is the core of the model configuration inheritance system.
    It takes a model's name and the dictionary of all configurations, then
    builds the final, flattened configuration for that model.

    It works by:
    1.  Checking for circular dependencies to prevent infinite recursion.
    2.  If the model `inherits` from a parent, it recursively calls itself to
        resolve the parent's configuration first.
    3.  It then merges the current model's specific settings into the resolved
        parent configuration, with the child's settings taking precedence.
    4.  The final, resolved configuration is cached to avoid redundant work.

    Args:
        name: The name of the model config to resolve.
        configs: A dictionary containing all model configurations.
        resolved_configs: A cache for storing already resolved configs.
        resolving_stack: A set used to track the current inheritance chain
                         to detect circular dependencies.

    Returns:
        A dictionary representing the fully resolved model configuration.

    Raises:
        ModelConfigError: If a circular dependency is detected or if a model
                          name is not found.
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
    """Loads and resolves all model configurations from a JSON file.

    This function serves as the main entry point for loading model settings.
    It reads a JSON file containing definitions for multiple models, then
    iterates through each model and uses the `_resolve_config` helper to
    build its complete configuration, resolving any `inherits` clauses.

    The result is a dictionary where keys are model names and values are their
    fully resolved configuration objects.

    Args:
        config_path: The file path to the JSON configuration file.

    Returns:
        A dictionary containing all resolved model configurations.

    Raises:
        ModelConfigError: If the config file is not found, cannot be parsed,
                          or contains circular dependencies.
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
    """Retrieves a specific model's config, with fallback to a default.

    This function safely retrieves a configuration from the dictionary of all
    resolved configs. If the specified `model_name` is not found, it attempts
    to fall back to a default configuration specified by `default_config_key`.
    It also ensures that the returned configuration dictionary has a `params`
    key, even if it's just an empty dictionary, to prevent downstream errors.

    Args:
        model_name: The name of the desired model configuration.
        all_configs: The dictionary of all available, resolved model configs.
        default_config_key: The key for the default configuration to use if
                            `model_name` is not found.

    Returns:
        A deep copy of the requested model's configuration dictionary.

    Raises:
        ModelConfigError: If the requested model is not found and no default
                          configuration is available.
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
