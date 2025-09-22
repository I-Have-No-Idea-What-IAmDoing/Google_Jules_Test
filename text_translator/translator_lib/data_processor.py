from typing import Any, Dict, List, Union
from langdetect import detect, LangDetectException

def collect_text_nodes(data: Union[Dict[str, Any], List[Any]], nodes_list: List[Dict[str, Any]]) -> None:
    """
    Recursively finds all text nodes in the data structure that need translation.

    A node needs translation if its key is `"#text"`, its value is a string,
    it is not already marked as processed (with `jp_text:::`), and its language
    is detected as non-English.

    Args:
        data: The nested dictionary or list to traverse.
        nodes_list: A list to which the dictionaries containing text nodes
                    (i.e., the parent dict of the '#text' key) are appended.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str):
                try:
                    if not value.startswith("jp_text:::") and detect(value) != 'en':
                        nodes_list.append(data)
                except LangDetectException:
                    nodes_list.append(data)
            else:
                collect_text_nodes(value, nodes_list)
    elif isinstance(data, list):
        for item in data:
            collect_text_nodes(item, nodes_list)

def cleanup_markers(data: Union[Dict[str, Any], List[Any]]) -> None:
    """
    Recursively removes the 'jp_text:::' processing marker from all text nodes.

    This is called after translation is complete to clean up the temporary
    markers used to prevent re-translation.

    Args:
        data: The nested dictionary or list to clean.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str) and value.startswith("jp_text:::"):
                data[key] = value.replace("jp_text:::", "", 1)
            else:
                cleanup_markers(value)
    elif isinstance(data, list):
        for item in data:
            cleanup_markers(item)
