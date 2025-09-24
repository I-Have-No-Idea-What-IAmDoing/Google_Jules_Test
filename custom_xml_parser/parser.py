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

    def flush_text_buffer():
        """Processes, dedents, and clears the text buffer into the current dictionary.

        This inner function dedents the collected text block to preserve relative
        indentation while removing the block-level indentation. This makes serialization
        cleaner as the serializer can apply its own indentation without conflicts.
        """
        if not text_buffer:
            return

        # --- DEDENT LOGIC ---
        lines_with_content = [line for line in text_buffer if line.strip()]
        if not lines_with_content:
            # All lines are empty or just whitespace.
            content = "\n".join(text_buffer)
        else:
            # Calculate the minimum indentation from lines that have content.
            min_indent = min(len(line) - len(line.lstrip()) for line in lines_with_content)
            # Strip the common indentation from all lines.
            # Lines that are only whitespace are preserved as-is.
            dedented_lines = [line[min_indent:] if line.strip() else line for line in text_buffer]
            content = "\n".join(dedented_lines)
        # --- END DEDENT LOGIC ---

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

        # Optimized tag handling without regex.
        # The order of checks is crucial. More specific tags must be checked before less specific ones.
        # A valid tag name itself cannot contain brackets or spaces. This check mimics the original regex.
        # 1. Closing standard tag: </tag>
        if stripped_line.startswith('</') and stripped_line.endswith('>'):
            tag_name = stripped_line[2:-1]
            if '<' not in tag_name and '>' not in tag_name and ' ' not in tag_name:
                flush_text_buffer()
                current_dict = dict_stack[-1]
                if comment_buffer:
                    if "#comments" not in current_dict:
                        current_dict["#comments"] = []
                    current_dict["#comments"].extend(comment_buffer)
                    comment_buffer.clear()

                if not tag_stack or tag_stack[-1] != ('<', tag_name):
                    raise ValueError(f"Mismatched closing tag '{stripped_line}' on line {line_num}")

                tag_stack.pop()
                dict_stack.pop()

                if comment_part:
                    comment_buffer.append(comment_part)
                continue
        # 2. Closing action tag: [/Action]
        elif stripped_line.startswith('[/') and stripped_line.endswith(']'):
            tag_name = stripped_line[2:-1]
            if '[' not in tag_name and ']' not in tag_name and ' ' not in tag_name:
                flush_text_buffer()
                current_dict = dict_stack[-1]
                if comment_buffer:
                    if "#comments" not in current_dict:
                        current_dict["#comments"] = []
                    current_dict["#comments"].extend(comment_buffer)
                    comment_buffer.clear()

                if not tag_stack or tag_stack[-1] != ('[', tag_name):
                    raise ValueError(f"Mismatched closing tag '{stripped_line}' on line {line_num}")

                tag_stack.pop()
                dict_stack.pop()

                if comment_part:
                    comment_buffer.append(comment_part)
                continue
        # 3. Opening standard tag: <tag>
        elif stripped_line.startswith('<') and stripped_line.endswith('>'):
            tag_name = stripped_line[1:-1]
            if '<' not in tag_name and '>' not in tag_name and ' ' not in tag_name:
                flush_text_buffer()
                new_dict = {}

                all_comments = comment_buffer
                if comment_part:
                    all_comments.append(comment_part)
                if all_comments:
                    new_dict["#comments"] = all_comments
                comment_buffer = []

                dict_stack[-1][tag_name] = new_dict
                dict_stack.append(new_dict)
                tag_stack.append(('<', tag_name))
                continue
        # 4. Opening action tag: [Action]
        elif stripped_line.startswith('[') and stripped_line.endswith(']'):
            tag_name = stripped_line[1:-1]
            if '[' not in tag_name and ']' not in tag_name and ' ' not in tag_name:
                flush_text_buffer()
                new_dict = {}

                all_comments = comment_buffer
                if comment_part:
                    all_comments.append(comment_part)
                if all_comments:
                    new_dict["#comments"] = all_comments
                comment_buffer = []

                dict_stack[-1][tag_name] = new_dict
                dict_stack.append(new_dict)
                tag_stack.append(('[', tag_name))
                continue

        # If a line is not a tag, it's treated as text content.
        # We append the original line to preserve indentation and inline comments.
        text_buffer.append(line)

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
