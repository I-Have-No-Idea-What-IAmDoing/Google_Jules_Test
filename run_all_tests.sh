#!/bin/bash
set -e
echo "--- Installing dependencies for text_translator ---"
pip install -r text_translator/requirements.txt
echo
echo "--- Running tests for custom_xml_parser ---"
python -m unittest custom_xml_parser.tests.test_parser
echo
echo "--- Running tests for text_translator ---"
python -m unittest text_translator.tests.test_cli text_translator.tests.test_core text_translator.tests.test_model_loader
echo
echo "✅ All checks passed successfully!"
