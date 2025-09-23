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
    It processes the text line by line, maintaining a stack of open tags and
    their corresponding dictionaries. It handles the hierarchical structure of
    action groups (`[GroupName]`) and standard tags (`<TagName>`).

    A key feature is the preservation of comments (`# ...`). Comments are
    buffered and associated with the next tag that is opened. Text content
    within a tag is stored under the `'#text'` key.

    The parser is stateful and relies on the order of lines. Mismatched or
    unclosed tags will result in a `ValueError`.

    Args:
        text: A string containing the data in the custom hierarchical format.
              It is expected to be a multi-line string.

    Returns:
        A nested dictionary representing the structured data. For example:
        `{'Action': {'#comments': ['...'], 'Tag': {'#text': '...'}}}`

    Raises:
        ValueError: If the parser encounters mismatched closing tags or if there
                    are unclosed tags at the end of the file.
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
        """Processes and clears the text buffer into the current dictionary.

        This inner function is called whenever a new tag is encountered or when
        the parsing of the file completes. It takes the lines of text collected
        in the `text_buffer`, joins them with newlines, and assigns the result
        to the `'#text'` key of the dictionary currently at the top of the
        `dict_stack`.

        If a `'#text'` key already exists in the current dictionary, the new
        content is appended to it, separated by a newline. This handles cases
        of interleaved text and tags. After processing, the `text_buffer` is
        cleared to prepare for the next block of text.
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
    """Recursively merges two dictionaries, giving precedence to the first.

    This function combines two dictionaries into a new, merged dictionary.
    The merging logic is as follows:
    - For keys present in both dictionaries, if both corresponding values are
      themselves dictionaries, the function will merge them recursively.
    - Otherwise, the value from the first dictionary (`d1`) is used.
    - Keys unique to either dictionary are included in the result.

    This is useful for combining a base configuration with a set of overrides.

    Args:
        d1: The primary dictionary, whose values take precedence in conflicts.
        d2: The secondary dictionary, whose values are used if the key is not
            present in `d1`.

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

    This function serves as the primary entry point for converting a dictionary
    (typically one created by `deserialize`) back into its string representation.
    It iterates through the top-level keys of the dictionary, which are expected
    to be action groups, and serializes each one.

    It gives special treatment to root-level comments (`'#comments'`) to ensure
    they appear at the top of the file, preserving file header comments. The
    actual serialization of nested content is handled by the `_serialize_content`
    helper function.

    Args:
        data: A nested dictionary representing the data structure. It is expected
              to follow the format produced by `deserialize`, including special
              keys like `'#comments'` and `'#text'`.

    Returns:
        A string containing the data serialized into the custom hierarchical
        format, with indentation and comments preserved.
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
    """Recursively serializes the content (text and tags) within a given dict.

    This helper function is responsible for formatting the content inside a tag,
    including its text value and any nested tags. It applies indentation based
    on the current nesting `level`.

    The serialization order is:
    1. The tag's own text content (`#text`).
    2. Any nested standard tags (`<TagName>`), each with its own content
       serialized recursively.

    Args:
        data: The dictionary representing the content of a tag. This dict may
              contain a `'#text'` key for its text value and other keys for
              nested tags.
        level: The current indentation level, used to create the correct tab
               spacing for pretty-printing the output.

    Returns:
        A string containing the serialized and indented content. If the data
        dict is empty (aside from special keys like `#comments`), it returns
        an empty string.
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
