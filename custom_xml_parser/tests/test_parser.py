import unittest
import os
import sys

from custom_xml_parser.parser import deserialize, serialize, merge

EXAMPLE_DATA = """
# 餌発見
[WantFood]
	<normal>
		<baby>
			ごはんしゃん！
			ごはんしゃんのにおいがすりゅわ！
			おいしそうにぇ！
			ゆっきゅりいただきまちゅ！
		</baby>
		<child>
			ごはんしゃん！
			ごはんしゃんのにおいがすりゅわ！
			おいしそうにぇ！
			ゆっきゅりいただきましゅ！
		</child>
		<adult>
			ごはんさんだわ！
			おいしそうなごはんさんね
			ごはんさんのにおいがするわ！
			ゆっくりいただきます！
		</adult>
	</normal>
	<rude>
		<baby>
			ときゃいは！ときゃいは！
			むーちゃむーちゃしゅりゅわ！
			%nameのごはんしゃん！
			%nameのむーちゃむーちゃたいみゅ はじみゃりゅわ！
			ときゃいはな%nameが たべてあげりゅわ！
		</baby>
		<child>
			ときゃいは！ときゃいは！
			むーしゃむーしゃしゅりゅわ！
			そのごはんしゃんは %nameのものよ！
			%nameのむーしゃむーしゃたいみゅ はじみゃりゅわ！
			ときゃいはな%nameが たべてあげりゅわ！
		</child>
		<adult>
			そのごはんさんは %nameのものよ！
			いなかくさいごはんさんはいやよ？
			%nameのむーしゃむーしゃたいむ はじまるわ！
		</adult>
	</rude>
[/WantFood]

# 餌なし
[NoFood]
	<normal>
		<baby>
			ごはんしゃんにゃいわよ？
			おにゃかへっちゃ！
			ごはんしゃんどこ？
			<damage>
				ごはんしゃんくだちゃい、、、
				おにゃかすいちゃわ、、、
				ままぁ、、たちゅけちぇ、、
			</damage>
		</baby>
		<child>
			ごはんしゃんにゃいわよ？
			おにゃかへっちゃ！
			ごはんしゃんどこ？
			<damage>
				ごはんしゃんくだしゃい、、、
				おにゃかすいちゃわ、、、
				ままぁ、、たしゅけちぇ、、、
			</damage>
		</child>
		<adult>
			ごはんさんがみつからないわ？
			%name おなかすいたわ！
			ごはんさんどこにあるのかしら？
			<damage>
				おながずいだぁ、、、
				どぼじでごはんさんどこにもないの、、、
				おねがいじまず、、ごはんさんぐだざい、、、
			</damage>
		</adult>
	</normal>
	<rude>
		<baby>
			はやく、ごはんしゃんもってきょい！
			おにゃかへっちゃ！
			いにゃかもにょー！
			<damage>
				はやく ごはんしゃんよこちぇ、、、
				おにゃかすいちゃわ、、、
				いにゃかもにょ、、、
				%nameをゆっきゅりさせにゃい くしょおやは、おたべなしゃいしりょ！
			</damage>
		</baby>
		<child>
			おにゃかへったー！
			ごはんしゃんにゃいわよ？ばかなの？しぬの？
			ごはんしゃんもっちぇこい！いなかもにょー！
			<damage>
				はやく ごはんしゃんよこしぇ、、、
				おにゃかすいちゃわ、、、
				いなかもにょ、、、
				%nameをゆっきゅりさせにゃい くしょおやは、おたべなしゃいしりょ！
			</damage>
		</child>
		<adult>
			%nameのごはんさんがないわよ？ばかなの？しぬの？
			いなかものはごはんさんももってこれないの？
			この、いなかものー！
			<damage>
				おながずいだあ゛ぁ、、、
				ごはんさんよごぜえぇ、、
				どぼじで ごはんさんどこにもないの、、、
				いながも゛の゛、、、
			</damage>
		</adult>
	</rude>
[/NoFood]
"""

class TestParser(unittest.TestCase):

    def test_round_trip_with_comments(self):
        """Tests that deserializing and then serializing results in the same data structure, including comments."""
        deserialized_data = deserialize(EXAMPLE_DATA)

        # Check that top-level comments are parsed
        self.assertIn("#comments", deserialized_data["WantFood"])
        self.assertIn("餌発見", deserialized_data["WantFood"]["#comments"][0])

        self.assertIn("#comments", deserialized_data["NoFood"])
        self.assertIn("餌なし", deserialized_data["NoFood"]["#comments"][0])

        serialized_data = serialize(deserialized_data)
        reserialized_data = deserialize(serialized_data)

        self.assertEqual(deserialized_data, reserialized_data)

    def test_inline_comment(self):
        """Tests that inline comments are parsed correctly."""
        data_with_inline_comment = "[Action] # This is an inline comment\n[/Action]"
        parsed = deserialize(data_with_inline_comment)
        self.assertIn("Action", parsed)
        self.assertIn("#comments", parsed["Action"])
        self.assertEqual(parsed["Action"]["#comments"], ["This is an inline comment"])

    def test_round_trip_preserves_inline_comment_on_text_line(self):
        """Tests that inline comments on text lines are preserved in a round trip."""
        data = """
[Action]
    <Setting>
        mode a  # This is a crucial comment.
    </Setting>
[/Action]
"""
        deserialized = deserialize(data)
        serialized = serialize(deserialized)

        # The crucial check: does the serialized output still have the comment?
        self.assertIn("# This is a crucial comment.", serialized)

    def test_empty_and_comments_only(self):
        """Tests deserializing empty strings or strings with only comments."""
        self.assertEqual(deserialize(""), {})
        self.assertEqual(deserialize("   "), {})
        self.assertEqual(deserialize("# this is a comment"), {"#comments": ["this is a comment"]})
        self.assertEqual(deserialize("\n# another comment\n"), {"#comments": ["another comment"]})

    def test_mismatched_tags(self):
        """Tests that mismatched tags raise a ValueError."""
        # Mismatched bracket types, e.g., [tag]...</tag>
        with self.assertRaises(ValueError, msg="Failed on [action]...</action>"):
            deserialize("[action]\n</action>")

        # Incorrectly nested tags
        with self.assertRaises(ValueError, msg="Failed on incorrect nesting"):
            deserialize("[action1]\n<tag2>\n[/action1]")

        # Mismatched closing tag name
        with self.assertRaises(ValueError, msg="Failed on wrong closing tag name"):
            deserialize("<tag>\n</tag_wrong>")

    def test_merge(self):
        """Tests the deep merging of two dictionaries."""
        d1 = {
            "action1": {
                "tag1": {"#text": "d1t1"},
                "tag2": {"#text": "d1t2"}
            },
            "action2": {"#text": "d1a2"}
        }
        d2 = {
            "action1": {
                "tag2": {"#text": "d2t2"}, # Should be ignored
                "tag3": {"#text": "d2t3"}  # Should be added
            },
            "action3": {"#text": "d2a3"} # Should be added
        }

        expected = {
            "action1": {
                "tag1": {"#text": "d1t1"},
                "tag2": {"#text": "d1t2"}, # From d1
                "tag3": {"#text": "d2t3"}  # From d2
            },
            "action2": {"#text": "d1a2"}, # From d1
            "action3": {"#text": "d2a3"}  # From d2
        }

        merged = merge(d1, d2)
        self.assertEqual(merged, expected)

        # Test with special keys
        d3 = {"tag": {"#text": "text1", "#comments": ["c1"]}}
        d4 = {"tag": {"#text": "text2", "#comments": ["c2"], "sub": {}}}

        expected2 = {"tag": {"#text": "text1", "#comments": ["c1"], "sub": {}}}
        merged2 = merge(d3, d4)
        self.assertEqual(merged2, expected2)


    def test_unclosed_tags(self):
        """Tests that unclosed tags raise a ValueError."""
        with self.assertRaises(ValueError):
            deserialize("[action]")
        with self.assertRaises(ValueError):
            deserialize("[action]\n<tag>")
        with self.assertRaises(ValueError):
            deserialize("[action]\n<tag>\n</tag>")


    def test_tag_with_hyphen(self):
        """Tests that tags with hyphens are parsed correctly."""
        data = """
[my-action]
    <my-tag>
        some-text
    </my-tag>
[/my-action]
"""
        parsed = deserialize(data)
        expected = {
            "my-action": {
                "my-tag": {
                    "#text": "some-text"
                }
            }
        }
        self.assertEqual(parsed, expected)


    def test_round_trip_for_root_comments(self):
        """Tests that root-level comments are preserved in a deserialize-serialize round trip."""
        comment_only_string = "# line 1\n# line 2"
        deserialized = deserialize(comment_only_string)
        self.assertEqual(deserialized, {"#comments": ["line 1", "line 2"]})

        serialized = serialize(deserialized)
        # The bug will cause `serialized` to be an empty string.
        # We expect the comments to be preserved.
        # Normalizing by deserializing again is a robust way to check for equivalence.
        reserialized_data = deserialize(serialized)
        self.assertEqual(deserialized, reserialized_data)

        # Also check the string output directly, accounting for formatting variations.
        self.assertIn("# line 1", serialized)
        self.assertIn("# line 2", serialized)


    def test_trailing_comment_in_block(self):
        """Tests that trailing comments in a block are associated with that block."""
        data = """
[Action]
    <Child>
        # This is a trailing comment inside Child.
    </Child>
[/Action]
"""
        parsed = deserialize(data)

        # The trailing comment should be associated with 'Child'.
        self.assertIn("Child", parsed["Action"])
        self.assertIn("#comments", parsed["Action"]["Child"])
        self.assertEqual(
            parsed["Action"]["Child"]["#comments"],
            ["This is a trailing comment inside Child."]
        )

        # Ensure the comment is not incorrectly attached to a parent or the root.
        self.assertNotIn("#comments", parsed)
        self.assertNotIn("#comments", parsed["Action"])


    def test_multiline_text_in_tag(self):
        """Tests that multiple lines of text within a single tag are correctly concatenated."""
        data = """
        <tag>
            line 1
            line 2
        </tag>
        """
        # This structure will not hit the += line, but it's the closest we can get
        # with the current parser implementation.
        parsed = deserialize(data)
        self.assertEqual(parsed['tag']['#text'], 'line 1\nline 2')

    def test_mismatched_closing_tag_error_specific(self):
        """A very specific test to trigger the mismatched tag error."""
        with self.assertRaisesRegex(ValueError, "Mismatched closing tag '</action>' on line 2"):
            deserialize("[action]\n</action>")

    def test_serialize_with_non_dict_value(self):
        """Tests that serializing a dictionary with non-dictionary values does not fail."""
        data = {"key1": "value1", "key2": {"#text": "text"}}
        serialized = serialize(data)
        # Top-level keys are serialized as action groups
        self.assertIn("[key2]", serialized)
        self.assertIn("text", serialized)
        self.assertNotIn("<key2>", serialized)
        self.assertNotIn("key1", serialized)
        self.assertNotIn("value1", serialized)


    def test_duplicate_comments_round_trip(self):
        """
        Tests that a round trip of deserialize -> serialize -> deserialize
        preserves duplicate comments.
        """
        data_with_duplicates = '''
# comment
[Action]
    # comment
    <Child1>
        # comment
        text1
    </Child1>
    # comment
    <Child2>
        # comment
        text2
    </Child2>
    # comment
[/Action]
# comment
'''
        deserialized_once = deserialize(data_with_duplicates)
        serialized_output = serialize(deserialized_once)
        deserialized_twice = deserialize(serialized_output)

        self.assertEqual(deserialized_once, deserialized_twice)


    def test_serialize_root_comments_first(self):
        """
        Tests that root-level comments are serialized before any action groups.
        """
        data = {
            "#comments": ["This is a root comment."],
            "MyAction": {
                "Settings": {
                    "#text": "mode a"
                }
            }
        }

        serialized = serialize(data)

        # The comment should appear before the action group.
        expected_prefix = "# This is a root comment."
        self.assertTrue(
            serialized.strip().startswith(expected_prefix),
            f"Expected output to start with '{expected_prefix}', but got:\n{serialized}"
        )

    def test_round_trip_with_root_and_action_comments(self):
        """
        Tests that a round trip preserves the distinction between root and action comments.
        """
        input_string = (
            "# This is a root comment.\\n"
            "\\n"
            "# This is an action comment.\\n"
            "[MyAction]\\n"
            "    <Data>info</Data>\\n"
            "[/MyAction]"
        ).replace("\\n", "\n")

        # 1. Deserialize the initial string
        d1 = deserialize(input_string)

        # Check initial deserialization is correct
        self.assertIn("#comments", d1)
        self.assertEqual(d1["#comments"], ["This is a root comment."])
        self.assertIn("MyAction", d1)
        self.assertIn("#comments", d1["MyAction"])
        self.assertEqual(d1["MyAction"]["#comments"], ["This is an action comment."])

        # 2. Serialize it back
        s2 = serialize(d1)

        # 3. Deserialize again
        d2 = deserialize(s2)

        # 4. Assert that the data structure is unchanged
        self.assertEqual(d1, d2)

    def test_interleaved_text_and_tags(self):
        """Tests that text before and after a nested tag is preserved correctly."""
        data = """
<tag>
    text before
    <nested>
        nested text
    </nested>
    text after
</tag>
"""
        parsed = deserialize(data)
        self.assertEqual(parsed['tag']['#text'], 'text before\ntext after')
        self.assertEqual(parsed['tag']['nested']['#text'], 'nested text')

    def test_trailing_comment_with_blank_line(self):
        """Tests that a trailing comment followed by a blank line is parsed correctly."""
        data = "[Action]\n# trailing comment\n\n[/Action]"
        parsed = deserialize(data)
        self.assertIn("#comments", parsed["Action"])
        self.assertEqual(parsed["Action"]["#comments"], ["trailing comment"])

    def test_mismatched_action_tag(self):
        """Tests that mismatched action tags raise a ValueError."""
        data = "[Action]\n</Action>"
        with self.assertRaises(ValueError):
            deserialize(data)


if __name__ == '__main__':
    unittest.main()
