import unittest
import sys
import os

# Add the parent directory to the path to find the parser module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parser import deserialize, serialize, merge

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


if __name__ == '__main__':
    unittest.main()
