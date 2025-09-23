import unittest
import os
from custom_xml_parser.parser import deserialize

class TestRealData(unittest.TestCase):

    def test_parse_yuyuko_ev_j_data(self):
        """Tests parsing of a real-world data file."""
        data_path = os.path.join(os.path.dirname(__file__), 'data', 'yuyuko_ev_j.txt')
        with open(data_path, 'r', encoding='utf-8') as f:
            data = f.read()

        parsed_data = deserialize(data)

        # Basic checks to ensure the data was parsed
        self.assertIn('WantFood', parsed_data)
        self.assertIn('NoFood', parsed_data)

        # Check for a nested tag
        self.assertIn('normal', parsed_data['WantFood'])
        self.assertIn('baby', parsed_data['WantFood']['normal'])
        self.assertIn('adult', parsed_data['WantFood']['normal'])

        # Check for text content
        self.assertIn('#text', parsed_data['WantFood']['normal']['baby'])
        self.assertIn('ごはんしゃん！', parsed_data['WantFood']['normal']['baby']['#text'])
        
    def test_parse_yuyuko_j_data(self):
        """Tests parsing of a real-world data file."""
        data_path = os.path.join(os.path.dirname(__file__), 'data', 'yuyuko_j.txt')
        with open(data_path, 'r', encoding='utf-8') as f:
            data = f.read()

        parsed_data = deserialize(data)

        # Basic checks to ensure the data was parsed
        self.assertIn('WantFood', parsed_data)
        self.assertIn('NoFood', parsed_data)

        # Check for a nested tag
        self.assertIn('normal', parsed_data['WantFood'])
        self.assertIn('baby', parsed_data['WantFood']['normal'])
        self.assertIn('adult', parsed_data['WantFood']['normal'])

        # Check for text content
        self.assertIn('#text', parsed_data['WantFood']['normal']['baby'])
        self.assertIn('ごはんしゃん！', parsed_data['WantFood']['normal']['baby']['#text'])

if __name__ == '__main__':
    unittest.main()
