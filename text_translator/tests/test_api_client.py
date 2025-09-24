import unittest
from unittest.mock import patch, MagicMock
from text_translator.translator_lib.api_client import ensure_model_loaded

class TestApiClient(unittest.TestCase):

    @patch('text_translator.translator_lib.api_client._api_request')
    def test_ensure_model_loaded_with_extra_flags_formatting(self, mock_api_request):
        """
        Verify that extra_flags are correctly formatted as a comma-separated string.
        """
        # Mock the server's response for the current model
        mock_api_request.return_value = {'model_name': 'some-other-model'}

        model_name = "test-model"
        api_base_url = "http://fake-url:5000"
        model_config = {
            "params": {"temperature": 0.5},
            "extra_flags": {
                "flag1": "value1",
                "flag2": "",
                "flag3": "value3"
            }
        }

        ensure_model_loaded(model_name, api_base_url, model_config)

        # The first call is to get model info, the second is to load the model
        self.assertEqual(mock_api_request.call_count, 2)

        # Get the arguments of the second call to _api_request
        call_args, call_kwargs = mock_api_request.call_args

        # The payload is the second positional argument
        payload = call_args[1]

        # Check that the payload has the correctly formatted extra_flags
        expected_flags = "flag1=value1,flag2,flag3=value3"
        self.assertIn("args", payload)
        self.assertIn("extra_flags", payload["args"])
        self.assertEqual(payload["args"]["extra_flags"], expected_flags)
        self.assertEqual(payload["args"]["temperature"], 0.5)

if __name__ == '__main__':
    unittest.main()