import re

def deserialize(text: str) -> dict:
    """
    Deserializes a string in the custom XML-like format into a nested dictionary.
    """
    lines = text.splitlines()

    root = {}
    dict_stack = [root]
    tag_stack = []
    text_buffer = []
    comment_buffer = []

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


def serialize(data: dict) -> str:
    """
    Serializes a nested dictionary into a string in the custom XML-like format.

    Args:
        data: The nested dictionary to serialize.

    Returns:
        A string in the custom format.
    """
    return _serialize_recursive(data, 0, True).strip()

def _serialize_recursive(data: dict, level: int, is_action_group: bool) -> str:
    result = []
    indent = "\t" * level

    # Root-level comments
    if "#comments" in data and level == 0:
        for comment in data["#comments"]:
            result.append(f"{indent}# {comment}")

    if "#text" in data:
        text_lines = data["#text"].split('\n')
        for line in text_lines:
            result.append(f"{indent}{line}")

    for key, value in data.items():
        if key.startswith("#"):
            continue

        if not isinstance(value, dict):
            # For simplicity, we assume values are dictionaries.
            continue

        # Comments associated with a specific tag
        if "#comments" in value:
            for comment in value["#comments"]:
                result.append(f"{indent}# {comment}")

        open_tag, close_tag = (f"[{key}]", f"[/{key}]") if is_action_group else (f"<{key}>", f"</{key}>")

        result.append(f"{indent}{open_tag}")
        # Nested items are always tag groups, so is_action_group is False for recursive calls.
        result.append(_serialize_recursive(value, level + 1, False))
        result.append(f"{indent}{close_tag}")

    return "\n".join(result)
