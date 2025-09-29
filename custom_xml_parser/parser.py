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
from typing import Any, Dict, List, Optional, Tuple


class _Parser:
    """
    A stateful parser to deserialize the custom XML-like format.

    This class encapsulates the entire state of the parsing process, including
    the stacks for open tags and dictionaries, and buffers for text and comments.
    It processes a file line by line, building the nested dictionary structure.

    The main entry point is the `deserialize` method. The public-facing
    `deserialize()` function in this module is a lightweight facade that
    instantiates this class and calls its `deserialize` method.
    """
    def __init__(self):
        self.root: Dict[str, Any] = {}
        self.dict_stack: List[Dict[str, Any]] = [self.root]
        self.tag_stack: List[Tuple[str, str]] = []
        self.text_buffer: List[str] = []
        self.comment_buffer: List[str] = []
        self.line_num: int = 0

    def _flush_text_buffer(self):
        """Processes, dedents, and clears the text buffer into the current dictionary."""
        if not self.text_buffer:
            return

        # Dedent the collected text block to preserve relative indentation.
        lines_with_content = [line for line in self.text_buffer if line.strip()]
        if not lines_with_content:
            content = "\n".join(self.text_buffer)
        else:
            min_indent = min(len(line) - len(line.lstrip()) for line in lines_with_content)
            dedented_lines = [line[min_indent:] if line.strip() else line for line in self.text_buffer]
            content = "\n".join(dedented_lines)

        if content:
            current_dict = self.dict_stack[-1]
            if "#text" in current_dict:
                current_dict["#text"] += "\n" + content
            else:
                current_dict["#text"] = content
        self.text_buffer.clear()

    def _is_valid_tag_name(self, name: str, is_action: bool = False) -> bool:
        """Checks if a tag name contains invalid characters (e.g., brackets, spaces)."""
        if is_action:
            return not ('[' in name or ']' in name or ' ' in name)
        else:
            return not ('<' in name or '>' in name or ' ' in name)

    def _handle_opening_tag(self, tag_name: str, tag_char: str, comment_part: Optional[str]):
        """Handles the logic for an opening tag."""
        self._flush_text_buffer()
        new_dict: Dict[str, Any] = {}

        all_comments = self.comment_buffer
        if comment_part:
            all_comments.append(comment_part)

        if all_comments:
            new_dict["#comments"] = all_comments
        self.comment_buffer = []

        self.dict_stack[-1][tag_name] = new_dict
        self.dict_stack.append(new_dict)
        self.tag_stack.append((tag_char, tag_name))

    def _handle_closing_tag(self, tag_name: str, tag_char: str, comment_part: Optional[str], raw_tag: str):
        """Handles the logic for a closing tag, including validation."""
        self._flush_text_buffer()
        current_dict = self.dict_stack[-1]

        if self.comment_buffer:
            if "#comments" not in current_dict:
                current_dict["#comments"] = []
            current_dict["#comments"].extend(self.comment_buffer)
            self.comment_buffer.clear()

        expected_tag = (tag_char, tag_name)
        if not self.tag_stack or self.tag_stack[-1] != expected_tag:
            raise ValueError(f"Mismatched closing tag '{raw_tag}' on line {self.line_num}")

        self.tag_stack.pop()
        self.dict_stack.pop()

        if comment_part:
            self.comment_buffer.append(comment_part)

    def _process_line(self, line: str):
        """Parses a single line and updates the parser's state."""
        self.line_num += 1
        parts = line.split('#', 1)
        code_part = parts[0]
        comment_part = parts[1].strip() if len(parts) > 1 else None
        stripped_line = code_part.strip()

        if not stripped_line:
            if comment_part:
                self.comment_buffer.append(comment_part)
            elif self.comment_buffer:
                current_dict = self.dict_stack[-1]
                if "#comments" not in current_dict:
                    current_dict["#comments"] = []
                current_dict["#comments"].extend(self.comment_buffer)
                self.comment_buffer.clear()
            if self.text_buffer:
                self.text_buffer.append("")
            return

        # --- TAG MATCHING LOGIC ---
        # 1. Closing standard tag: </tag>
        if stripped_line.startswith('</') and stripped_line.endswith('>'):
            tag_name = stripped_line[2:-1]
            if self._is_valid_tag_name(tag_name):
                self._handle_closing_tag(tag_name, '<', comment_part, stripped_line)
                return
        # 2. Closing action tag: [/Action]
        elif stripped_line.startswith('[/') and stripped_line.endswith(']'):
            tag_name = stripped_line[2:-1]
            if self._is_valid_tag_name(tag_name, is_action=True):
                self._handle_closing_tag(tag_name, '[', comment_part, stripped_line)
                return
        # 3. Opening standard tag: <tag>
        elif stripped_line.startswith('<') and stripped_line.endswith('>'):
            tag_name = stripped_line[1:-1]
            if self._is_valid_tag_name(tag_name):
                self._handle_opening_tag(tag_name, '<', comment_part)
                return
        # 4. Opening action tag: [Action]
        elif stripped_line.startswith('[') and stripped_line.endswith(']'):
            tag_name = stripped_line[1:-1]
            if self._is_valid_tag_name(tag_name, is_action=True):
                self._handle_opening_tag(tag_name, '[', comment_part)
                return

        # If no tag matched, it's text content.
        self.text_buffer.append(line)

    def deserialize(self, text: str) -> Dict[str, Any]:
        """Main entry point for the parser instance. Processes the entire text."""
        lines = text.splitlines()
        for line in lines:
            self._process_line(line)

        self._flush_text_buffer()

        if self.comment_buffer:
            if "#comments" not in self.root:
                self.root["#comments"] = []
            self.root["#comments"].extend(self.comment_buffer)

        if self.tag_stack:
            raise ValueError(f"Unclosed tags at end of file: {self.tag_stack}")

        return self.root


def deserialize(text: str) -> Dict[str, Any]:
    """Deserializes a string in a custom XML-like format into a dictionary.

    This function is a facade that instantiates a stateful parser and runs it.
    It processes the text line by line, maintaining a stack of open tags and
    their corresponding dictionaries. It handles the hierarchical structure of
    action groups (`[GroupName]`) and standard tags (`<TagName>`).

    Args:
        text: A string containing the data in the custom hierarchical format.

    Returns:
        A nested dictionary representing the structured data.

    Raises:
        ValueError: If the parser encounters mismatched or unclosed tags.
    """
    parser = _Parser()
    return parser.deserialize(text)


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

    Args:
        data: A nested dictionary representing the data structure.

    Returns:
        A string containing the data serialized into the custom hierarchical
        format, with indentation and comments preserved.
    """
    result = []

    if "#comments" in data:
        for comment in data["#comments"]:
            result.append(f"# {comment}")
        if any(not k.startswith("#") for k in data.keys()):
            result.append("")

    for key, value in data.items():
        if key.startswith("#") or not isinstance(value, dict):
            continue

        if "#comments" in value:
            for comment in value["#comments"]:
                result.append(f"# {comment}")

        result.append(f"[{key}]")
        content = _serialize_content(value, 1)
        if content:
            result.append(content)
        result.append(f"[/{key}]")

    return "\n".join(result)


def _serialize_content(data: Dict[str, Any], level: int) -> str:
    """Recursively serializes the content (text and tags) within a given dict."""
    result: List[str] = []
    indent = "\t" * level

    if "#text" in data:
        for line in data["#text"].split('\n'):
            result.append(f"{indent}{line}")

    for key, value in data.items():
        if key.startswith("#") or not isinstance(value, dict):
            continue

        if "#comments" in value:
            for comment in value["#comments"]:
                result.append(f"{indent}# {comment}")

        result.append(f"{indent}<{key}>")
        content = _serialize_content(value, level + 1)
        if content:
            result.append(content)
        result.append(f"{indent}</{key}>")

    return "\n".join(result)