import requests
import sys
import os
import time
import json
from typing import Any, Dict

DEFAULT_API_BASE_URL: str = "http://127.0.0.1:5000/v1"

def _api_request(endpoint: str, payload: Dict[str, Any], api_base_url: str, timeout: int = 60, is_get: bool = False, debug: bool = False) -> Dict[str, Any]:
    """Sends a request to the API and handles the response.

    This is a centralized helper function for all communication with the LLM
    API. It abstracts away the details of `requests`, including setting headers,
    handling JSON serialization, and raising a standard `ConnectionError` on
    failure.

    Args:
        endpoint: The API endpoint to target (e.g., "chat/completions").
        payload: The dictionary to be sent as the JSON body of the request.
        api_base_url: The base URL of the API server.
        timeout: The timeout for the request in seconds.
        is_get: If True, performs a GET request; otherwise, a POST request.
        debug: If True, prints the full request payload and response to stderr.

    Returns:
        The JSON response from the API, parsed into a dictionary.

    Raises:
        ConnectionError: If the request fails due to a network issue, a timeout,
                         or an HTTP error status code from the server.
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
    """Checks if the API server is running and available.

    This function sends a simple request to a known informational endpoint on
    the server. If the request fails (e.g., due to a `ConnectionError`), it
    is assumed the server is not running. In this case, it prints a user-friendly
    error message and terminates the script with a non-zero exit code.

    Args:
        api_base_url: The base URL of the API server to check.
        debug: If True, passes the debug flag to the underlying API request
               for more detailed output.
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
    """Ensures the correct model is loaded on the API server.

    This function first queries the server to get the name of the currently
    loaded model. If it does not match the `model_name` parameter, it sends a
    new request to load the correct model and then pauses briefly to allow the
    server to complete the operation. This is essential for workflows that use
    multiple models (e.g., draft and refine).

    Args:
        model_name: The name of the model that needs to be loaded.
        api_base_url: The base URL of the API server.
        verbose: If True, prints status messages when a model switch occurs.
        debug: If True, passes the debug flag to underlying API requests.

    Raises:
        ConnectionError: If the function fails to get the current model info or
                         if the request to load a new model fails.
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
