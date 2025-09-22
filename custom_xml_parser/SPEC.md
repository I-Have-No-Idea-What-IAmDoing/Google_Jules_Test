# Custom Message Format Specification

## 1. Overview

This document specifies a custom text-based data format that resembles XML but with distinct syntax and structural rules. It is designed for organizing hierarchical data for message and dialogue systems.

The format is line-oriented and hierarchical. It supports two types of tags, comments, multi-line text content, variable substitution, and a detailed, state-based algorithm for conditional message selection.

## 2. File Structure

A file in this format consists of one or more **Action Groups**. These groups are the top-level elements of the document.

```
# Optional file-level comments

[FirstActionGroup]
  ...
[/FirstActionGroup]

# Comments between action groups
[SecondActionGroup]
  ...
[/SecondActionGroup]
```

## 3. Tag Syntax

### 3.1. Action Tags

- **Purpose**: Define top-level "action" or "event" containers.
- **Syntax**: Enclosed in square brackets `[]`.
- **Opening Tag**: `[TagName]`
- **Closing Tag**: `[/TagName]`

### 3.2. Standard Tags

- **Purpose**: Define nested data elements and conditional states within an Action Group.
- **Syntax**: Enclosed in angle brackets `<>`.
- **Opening Tag**: `<TagName>`
- **Closing Tag**: `</TagName>`

### 3.3. Tag Naming Rules

- Tag names are case-sensitive and must match the tags expected by the parser (e.g., `normal`, `baby`, `damage`).
- They can contain alphanumeric characters, underscores (`_`), hyphens (`-`), and periods (`.`).

## 4. Hierarchy and Nesting

- An **Action Group** contains one or more conditional blocks defined by **Standard Tags**.
- **Standard Tags** are nested to create a specific conditional path. The order of nesting defines the context for the text content within.

---

## 5. Message Selection Algorithm

The system selects a message using a precise, state-based algorithm. The nested tags define the conditions under which a message is chosen.

### 5.1. Key Construction and Fallback

The parser builds a key by appending condition names in a fixed order. It attempts to find a message at each step, creating a fallback system.

1.  **Base Key**: The key begins with either `normal_` or `rude_`, based on the character's mood. The parser immediately checks for a message at this base level (e.g., text directly inside `<normal>`). If found, this becomes the current "best available message".

2.  **Key Refinement**: The parser appends keys for other states in the following, strict order. After appending each new key, it checks for a corresponding message. If a message is found for the more specific key, it replaces the "best available message".

    **Evaluation Order:**
    1.  **Age State** (`baby_`, `child_`, or `adult_`)
    2.  **Damage State** (`damage_`)
    3.  **Foot Bake State** (`footbake_`)
    4.  **Pants State** (`pants_`)
    5.  **Player Love State** (`loveplayer_` or `dislikeplayer_`)
    6.  **Rank State** (`ununSlave_`)
    7.  **Intelligence State** (`wise_` or `fool_`)

### 5.2. Example of Algorithm

Consider a character who is an `adult` and `damaged`.
1.  The base key is `normal_`. The parser finds any messages directly within `<normal>` and sets them as the best available.
2.  The `adult_` key is appended. The new key is `normal_adult_`. The parser looks for messages inside `<normal><adult>`. If found, these new messages become the best available.
3.  The `damage_` key is appended. The new key is `normal_adult_damage_`. The parser looks for messages inside `<normal><adult><damage>`. If found, these become the best available.
4.  After all checks, the system uses the final "best available message". In this case, if a message existed for `normal_adult_damage_`, it's used. If not, but one existed for `normal_adult_`, that one is used instead.

### 5.3. Randomization

If multiple lines of text are valid for the final chosen condition, one line is selected at random.

## 6. Variable Substitution

Text content can contain placeholder variables that are replaced with dynamic values.

- **Syntax**: Variables consist of a percent sign (`%`) followed by the variable name (e.g., `%name`). **There is no trailing percent sign.**

- **Standard Variables**:
  - `%name`: Replaced with the primary name of the character.
  - `%name2`: Replaced with a secondary name or title.
  - `%partner`: Replaced with the name of the character's partner.

- **Special Variables**:
  - `%dummy`: If a chosen message line contains this variable, the application must treat it as a null or empty message, effectively silencing the character for that action.

**Example:**
```
<baby>
    %nameのごはんしゃん！ # Correct syntax
    %dummy%             # Results in no message
</baby>
```

## 7. Comments

- **Syntax**: Comments begin with a hash symbol (`#`) and continue to the end of the line.
- **Behavior**: Comment handling differs between parsers:
  - The original **Java-based parser** completely **ignores** comment lines. They are stripped from the file during processing and are not associated with any tags.
  - This **Python-based parser** implements an enhanced behavior: it **preserves** comments and associates them with the tags they precede or accompany. This is useful for round-trip serialization (reading, modifying, and writing a file) without losing documentation.
---

## 8. Complete Example

Here is an annotated example illustrating the rules:

```
# A character wants to find food.
[WantFood]
    # Messages for a 'normal' mood. This is the first level of fallback.
    <normal>
        ごはんがたべたいな。
        # For babies. This is a more specific context.
        <baby>
            %nameのごはんしゃん！
            ごはんしゃんこっちにきょい！
        </baby>
        # For adults.
        <adult>
            %nameのごはんさんのにおいがするよ！
            # A highly specific message for a damaged adult.
            <damage>
                ごはんざんぐだざいぃ、、、
            </damage>
        </adult>
    </normal>

    # Messages for a 'rude' mood.
    <rude>
        <adult>
            おい、じじぃ！にくにくあまあまちょうだいね！
        </adult>
    </rude>
[/WantFood]
```
