# Custom XML-like Parser

This module provides a serializer and deserializer for a custom XML-like data format.

The format has the following characteristics:
- Comments start with `#` and extend to the end of the line.
- Action groups are defined by `[GroupName]` and `[/GroupName]`.
- Tag groups are defined by `<TagName>` and `</TagName>`.
- The data is hierarchical, and the order of fields within a group does not matter.

## Comment Handling

A key feature of this parser is that it preserves comments. Comments are associated with the tag they precede and are stored in a special `"#comments"` key. This allows for round-trip serialization without losing documentation.

## Data Structure

The `deserialize` function converts the custom format into a nested Python dictionary. Text content within a tag is stored under a special `"#text"` key.

When a tag contains both text and other tags, the text is stored alongside the nested tags in the same dictionary.

## Usage

Below are examples of how to use the `deserialize` and `serialize` functions.

### Deserialization (String to Dictionary)

To parse a string in the custom format, use the `deserialize` function.

```python
from parser import deserialize

data_string = """
# This is a file header comment.

# This comment is for MyAction.
[MyAction]
    <Settings>
        mode a  # This is an inline comment.
        <level>5</level>
    </Settings>
[/MyAction]
"""

parsed_data = deserialize(data_string)
print(parsed_data)
# Output:
# {
#     '#comments': ['This is a file header comment.'],
#     'MyAction': {
#         '#comments': ['This comment is for MyAction.'],
#         'Settings': {
#             '#text': 'mode a',
#             'level': {
#                 '#text': '5'
#             }
#         }
#     }
# }
```

### Serialization (Dictionary to String)

To convert a dictionary back into the custom format string, use the `serialize` function.

```python
from parser import serialize

data_dict = {
    'MyAction': {
        'Settings': {
            '#text': 'mode a',
            'level': {
                '#text': '5'
            }
        }
    }
}

serialized_string = serialize(data_dict)
print(serialized_string)
# Output:
# [MyAction]
# 	<Settings>
# 		mode a
# 		<level>
# 			5
# 		</level>
# 	</Settings>
# [/MyAction]
```
