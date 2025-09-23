"""
Provides functions to serialize and deserialize a custom XML-like data format.

This parser handles a hierarchical data structure with two types of tags:
- Action Groups: `[GroupName]` ... `[/GroupName]` (top-level)
- Standard Tags: `<TagName>` ... `</TagName>` (nested)

A key feature of this parser is its handling of comments. Comments (`#...`) are
not discarded but are preserved and associated with the tags they precede or
accompany. They are stored in a special `"#comments"` key within a tag's dictionary.

The deserialized format is a nested dictionary where tags are keys and their
content (text and other tags) are values. Text content is stored under a
special `"#text"` key.
"""
import re
from typing import Any, Dict, List, Tuple

def deserialize(text: str) -> Dict[str, Any]:
    """Deserializes a string in a custom XML-like format into a dictionary.

    This function serves as the primary entry point for parsing the custom format.
    It processes the text line by line, building a nested dictionary that mirrors
    the hierarchical structure of action groups (`[GroupName]`) and standard tags
    (`<TagName>`).

    A key feature is the preservation of comments (`# ...`). Comments are
    associated with the tag they immediately precede and are stored in a special
    `'#comments'` key. Text content within a tag is stored under the `'#text'` key.

    Args:
        text: A string containing the data in the custom hierarchical format.

    Returns:
        A nested dictionary representing the structured data. For example:
        `{'Action': {'#comments': ['...'], 'Tag': {'#text': '...'}}}`

    Raises:
        ValueError: If the parser encounters mismatched or unclosed tags,
                    indicating a malformed structure.
    """
    lines = text.splitlines()

    root: Dict[str, Any] = {}
    dict_stack: List[Dict[str, Any]] = [root]
    tag_stack: List[Tuple[str, str]] = []
    text_buffer: List[str] = []
    comment_buffer: List[str] = []

    action_start_re = re.compile(r'^\s*\[([a-zA-Z0-9_.-]+)\]\s*$')
    action_end_re = re.compile(r'^\s*\[/([a-zA-Z0-9_.-]+)\]\s*$')
    tag_start_re = re.compile(r'^\s*<([a-zA-Z0-9_.-]+)>\s*$')
    tag_end_re = re.compile(r'^\s*</([a-zA-Z0-9_.-]+)>\s*$')

    def flush_text_buffer():
        """Processes and clears the text buffer.

        Joins the lines collected in `text_buffer` and adds them as a '#text'
        entry to the dictionary currently at the top of the `dict_stack`.
        If a '#text' entry already exists, the new content is appended.
        """
        if text_buffer:
            content = "\n".join(text_buffer)
            if content:
                current_dict = dict_stack[-1]
                if "#text" in current_dict:
                    current_dict["#text"] += "\n" + content
                else:
                    current_dict["#text"] = content
            text_buffer.clear()

    for line_num, line in enumerate(lines, 1):
        parts = line.split('#', 1)
        code_part = parts[0]
        comment_part = parts[1].strip() if len(parts) > 1 else None
        stripped_line = code_part.strip()

        if not stripped_line:
            if comment_part is not None and comment_part:
                comment_buffer.append(comment_part)
            # A blank line acts as a separator for comments.
            elif comment_buffer:
                current_dict = dict_stack[-1]
                if "#comments" not in current_dict:
                    current_dict["#comments"] = []
                current_dict["#comments"].extend(comment_buffer)
                comment_buffer.clear()

            if text_buffer:
                text_buffer.append("")
            continue

        # Handle start tags
        is_action = stripped_line.startswith('[')
        match = action_start_re.match(stripped_line) or tag_start_re.match(stripped_line)
        if match:
            flush_text_buffer()
            tag_name = match.group(1)
            new_dict = {}

            # Associate comments with this new tag
            all_comments = comment_buffer
            if comment_part:
                all_comments.append(comment_part)
            if all_comments:
                new_dict["#comments"] = all_comments
            comment_buffer = [] # Reset buffer

            dict_stack[-1][tag_name] = new_dict
            dict_stack.append(new_dict)
            tag_stack.append(('[' if is_action else '<', tag_name))
            continue

        # Handle end tags
        is_action_end = stripped_line.startswith('[/')
        match = action_end_re.match(stripped_line) or tag_end_re.match(stripped_line)
        if match:
            flush_text_buffer()

            # Before closing the current scope, associate buffered comments with it.
            current_dict = dict_stack[-1]
            if comment_buffer:
                if "#comments" not in current_dict:
                    current_dict["#comments"] = []
                current_dict["#comments"].extend(comment_buffer)
                comment_buffer.clear()

            tag_name = match.group(1)
            expected_bracket = '[' if is_action_end else '<'
            if not tag_stack or tag_stack[-1] != (expected_bracket, tag_name):
                raise ValueError(f"Mismatched closing tag '{stripped_line}' on line {line_num}")

            tag_stack.pop()
            dict_stack.pop()

            if comment_part: # Comment on a closing tag line
                comment_buffer.append(comment_part)
            continue

        text_buffer.append(stripped_line)

    flush_text_buffer()

    if comment_buffer:
        if "#comments" not in root:
            root["#comments"] = []
        root["#comments"].extend(comment_buffer)
        comment_buffer.clear()

    if tag_stack:
        raise ValueError(f"Unclosed tags at end of file: {tag_stack}")

    return root


def merge(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges two dictionaries with a "left-hand" priority.

    This function combines two dictionaries into a new one. The merge strategy is:
    - If a key exists in `d1` but not `d2`, it is kept.
    - If a key exists in `d2` but not `d1`, it is added.
    - If a key exists in both, the value from `d1` is used (it has priority).
    - If a key exists in both and both values are dictionaries, the function
      will recursively merge these nested dictionaries.

    Args:
        d1: The primary dictionary, whose values take precedence.
        d2: The secondary dictionary, whose values are used as fallbacks.

    Returns:
        A new dictionary containing the merged key-value pairs.
    """
    merged = d1.copy()
    for key, value in d2.items():
        if key in merged:
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def serialize(data: Dict[str, Any]) -> str:
    """Serializes a nested dictionary into a custom XML-like formatted string.

    This function converts a dictionary (typically one created by `deserialize`)
    back into its string representation. It handles the nesting of action groups
    (`[GroupName]`) and standard tags (`<TagName>`), preserves comments, and
    applies indentation to reflect the hierarchy.

    Args:
        data: A nested dictionary representing the data structure. It should
              follow the format used by `deserialize`, using keys like
              `'#comments'` and `'#text'`.

    Returns:
        A string containing the data serialized into the custom format.
    """
    result = []

    # Serialize root-level comments first to preserve file header comments.
    if "#comments" in data:
        for comment in data["#comments"]:
            result.append(f"# {comment}")
        # Add a newline to separate from the first action group if necessary.
        if any(not k.startswith("#") for k in data.keys()):
            result.append("")

    # Process top-level action groups.
    for key, value in data.items():
        if key.startswith("#") or not isinstance(value, dict):
            continue

        # Comments for the action group tag come before the tag itself.
        if "#comments" in value:
            for comment in value["#comments"]:
                result.append(f"# {comment}")

        result.append(f"[{key}]")
        # The helper function serializes the content *inside* the action group.
        content = _serialize_content(value, 1)
        if content:
            result.append(content)
        result.append(f"[/{key}]")

    return "\n".join(result)


def _serialize_content(data: Dict[str, Any], level: int) -> str:
    """
    Recursively serializes the content (text and standard tags) within a tag.
    """
    result: List[str] = []
    indent = "\t" * level

    # Text content is always output first at its level.
    if "#text" in data:
        # Split and re-indent to handle multiline text correctly.
        for line in data["#text"].split('\n'):
            result.append(f"{indent}{line}")

    # Then, process nested standard tags.
    for key, value in data.items():
        if key.startswith("#") or not isinstance(value, dict):
            continue

        # Comments for the nested tag come before the tag itself.
        if "#comments" in value:
            for comment in value["#comments"]:
                result.append(f"{indent}# {comment}")

        result.append(f"{indent}<{key}>")
        # The recursive call serializes the content *inside* the nested tag.
        content = _serialize_content(value, level + 1)
        if content:
            result.append(content)
        result.append(f"{indent}</{key}>")

    return "\n".join(result)
