import unittest
import os
import json
from text_translator.translator_lib.model_loader import load_model_configs, get_model_config, ModelConfigError

class TestModelLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(__file__)
        self.config_path = os.path.join(self.test_dir, 'models.json')

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def _write_config(self, data):
        with open(self.config_path, 'w') as f:
            json.dump(data, f)

    def test_load_model_configs_success(self):
        config_data = {
            "model_a": {"params": {"key": "value_a"}},
            "model_b": {"inherits": "model_a", "params": {"key": "value_b"}}
        }
        self._write_config(config_data)
        resolved_configs = load_model_configs(self.config_path)
        self.assertIn("model_a", resolved_configs)
        self.assertIn("model_b", resolved_configs)
        self.assertEqual(resolved_configs["model_b"]["params"]["key"], "value_b")

    def test_load_model_configs_inheritance(self):
        config_data = {
            "base": {"params": {"p1": "v1", "p2": "v2"}},
            "child": {"inherits": "base", "params": {"p2": "override"}}
        }
        self._write_config(config_data)
        resolved_configs = load_model_configs(self.config_path)
        self.assertEqual(resolved_configs["child"]["params"]["p1"], "v1")
        self.assertEqual(resolved_configs["child"]["params"]["p2"], "override")

    def test_load_model_configs_file_not_found(self):
        with self.assertRaises(ModelConfigError):
            load_model_configs("non_existent_file.json")

    def test_load_model_configs_invalid_json(self):
        with open(self.config_path, 'w') as f:
            f.write("{'invalid_json':}")
        with self.assertRaises(ModelConfigError):
            load_model_configs(self.config_path)

    def test_load_model_configs_non_existent_parent(self):
        config_data = {"child": {"inherits": "non_existent_parent"}}
        self._write_config(config_data)
        with self.assertRaises(ModelConfigError):
            load_model_configs(self.config_path)

    def test_get_model_config_success(self):
        all_configs = {"model_a": {"params": {"key": "value_a"}}}
        config = get_model_config("model_a", all_configs)
        self.assertEqual(config["params"]["key"], "value_a")

    def test_get_model_config_fallback_to_default(self):
        all_configs = {"_default": {"params": {"key": "default_value"}}}
        config = get_model_config("non_existent_model", all_configs)
        self.assertEqual(config["params"]["key"], "default_value")

    def test_get_model_config_no_model_no_default(self):
        all_configs = {"model_a": {"params": {}}}
        with self.assertRaises(ModelConfigError):
            get_model_config("non_existent_model", all_configs)

    def test_get_model_config_adds_missing_params_key(self):
        all_configs = {"model_a": {}}
        config = get_model_config("model_a", all_configs)
        self.assertIn("params", config)
        self.assertEqual(config["params"], {})

if __name__ == '__main__':
    unittest.main()
