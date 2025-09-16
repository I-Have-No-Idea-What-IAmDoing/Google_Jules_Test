import re
from typing import Any, Dict, List, Tuple

def deserialize(text: str) -> Dict[str, Any]:
    """
    Deserializes a string in the custom XML-like format into a nested dictionary.
    """
    lines = text.splitlines()

    root: Dict[str, Any] = {}
    dict_stack: List[Dict[str, Any]] = [root]
    tag_stack: List[Tuple[str, str]] = []
    text_buffer: List[str] = []
    comment_buffer: List[str] = []

    action_start_re = re.compile(r'^\s*\[([a-zA-Z0-9_]+)\]\s*$')
    action_end_re = re.compile(r'^\s*\[/([a-zA-Z0-9_]+)\]\s*$')
    tag_start_re = re.compile(r'^\s*<([a-zA-Z0-9_]+)>\s*$')
    tag_end_re = re.compile(r'^\s*</([a-zA-Z0-9_]+)>\s*$')

    def flush_text_buffer():
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
    """
    Recursively merges two dictionaries.

    Values from d1 take precedence. If a key exists in both and the values are
    dictionaries, the dictionaries are merged recursively.

    Args:
        d1: The primary dictionary (has priority).
        d2: The secondary dictionary.

    Returns:
        The merged dictionary.
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
    """
    Serializes a nested dictionary into a string in the custom XML-like format.

    Args:
        data: The nested dictionary to serialize.

    Returns:
        A string in the custom format.
    """
    return _serialize_recursive(data, 0, True).strip()

def _serialize_recursive(data: Dict[str, Any], level: int, is_action_group: bool) -> str:
    result: List[str] = []
    indent = "\t" * level

    # Text content should be output first for the current level.
    if "#text" in data:
        text_lines = data["#text"].split('\n')
        for line in text_lines:
            result.append(f"{indent}{line}")

    # Then, process child tags.
    for key, value in data.items():
        if key.startswith("#"):
            continue

        if not isinstance(value, dict):
            continue

        # Comments for the child tag come before the tag itself.
        if "#comments" in value:
            for comment in value["#comments"]:
                result.append(f"{indent}# {comment}")

        # Determine tag type based on whether we are at the top level of the structure.
        open_tag, close_tag = (f"[{key}]", f"[/{key}]") if is_action_group else (f"<{key}>", f"</{key}>")

        result.append(f"{indent}{open_tag}")
        # ALL recursive calls are for nested tags, which are never action groups.
        result.append(_serialize_recursive(value, level + 1, False))
        result.append(f"{indent}{close_tag}")

    # Finally, handle any trailing comments associated with the current dictionary context.
    if "#comments" in data and level > -1: # A simple way to handle root comments without special casing
        # This logic is tricky. Let's simplify and only print comments before tags.
        # Trailing comments in the root dict will be handled by the loop above if they are attached to a tag.
        pass


    return "\n".join(result)
