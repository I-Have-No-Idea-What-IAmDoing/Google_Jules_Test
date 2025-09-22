import requests
import sys
import os
import time
import json
from typing import Any, Dict

DEFAULT_API_BASE_URL: str = "http://127.0.0.1:5000/v1"

def _api_request(endpoint: str, payload: Dict[str, Any], api_base_url: str, timeout: int = 60, is_get: bool = False, debug: bool = False) -> Dict[str, Any]:
    """
    Sends a request to the specified API endpoint and handles responses.

    This is a low-level helper for communicating with the API. It wraps the
    `requests` library to handle POST/GET requests, JSON serialization, and
    common exceptions.

    Args:
        endpoint: The API endpoint to target (e.g., "completions").
        payload: The dictionary to send as a JSON payload.
        api_base_url: The base URL of the API server.
        timeout: The request timeout in seconds.
        is_get: If True, sends a GET request; otherwise, sends a POST request.
        debug: If True, prints the request payload and response.

    Returns:
        The JSON response from the API as a dictionary.

    Raises:
        ConnectionError: If the request fails due to a network error or an
                         unsuccessful HTTP status code.
    """
    headers = {"Content-Type": "application/json"}
    if debug:
        print(f"\n--- DEBUG: API Request to endpoint: {endpoint} ---", file=sys.stderr)
        print(f"--- DEBUG: API Request Payload ---\n{json.dumps(payload, indent=2)}\n-------------------------------------", file=sys.stderr)

    try:
        if is_get:
            response = requests.get(f"{api_base_url}/{endpoint}", timeout=timeout)
        else:
            response = requests.post(f"{api_base_url}/{endpoint}", json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        response_data = response.json()

        if debug:
            print(f"--- DEBUG: API Response ---\n{json.dumps(response_data, indent=2)}\n--------------------------------", file=sys.stderr)

        return response_data
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API request to {endpoint} failed: {e}")

def check_server_status(api_base_url: str, debug: bool = False) -> None:
    """
    Checks if the translation API server is running and available.

    Sends a request to a known endpoint. If the request fails, it prints an
    error message and terminates the program.

    Args:
        api_base_url: The base URL of the API server.
        debug: If True, prints debug information for the check.
    """
    if debug:
        print(f"--- DEBUG: Checking server status at {api_base_url} ---", file=sys.stderr)
    try:
        _api_request("internal/model/info", {}, api_base_url, is_get=True, timeout=10, debug=debug)
        if debug:
            print(f"--- DEBUG: Server is active. ---", file=sys.stderr)
    except ConnectionError:
        print(
            f"\n---FATAL ERROR---\n"
            f"Could not connect to the translation API server at '{api_base_url}'.\n"
            f"Please ensure the oobabooga web UI server is running and the API is enabled.\n"
            f"-------------------\n",
            file=sys.stderr
        )
        sys.exit(1)

def ensure_model_loaded(model_name: str, api_base_url: str, verbose: bool = False, debug: bool = False) -> None:
    """
    Ensures the specified model is loaded on the API server.

    Queries the server for the currently loaded model. If it does not match
    the desired model, this function sends a request to load the correct one
    and waits for it to complete.

    Args:
        model_name: The name of the model that should be loaded.
        api_base_url: The base URL of the API server.
        verbose: If True, prints status messages about model switching.
        debug: If True, passes debug flag to the underlying API request.

    Raises:
        ConnectionError: If it fails to get the current model or load the new one.
    """
    try:
        current_model_data = _api_request("internal/model/info", {}, api_base_url, is_get=True, debug=debug)
        current_model = current_model_data.get("model_name")
    except (ConnectionError, KeyError) as e:
        raise ConnectionError(f"Error getting current model: {e}")

    if current_model != model_name:
        if verbose:
            print(f"Switching model from '{current_model}' to '{model_name}'...")
        try:
            _api_request("internal/model/load", {"model_name": model_name}, api_base_url, timeout=300, debug=debug)
            if verbose: print("Model loaded successfully.")
            time.sleep(5)
        except ConnectionError as e:
            raise ConnectionError(f"Failed to load model '{model_name}': {e}")
