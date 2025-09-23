# Agent Instructions

Welcome, agent! This document provides instructions for working in this repository. Adhering to these guidelines will help ensure smooth collaboration and high-quality code.

## 1. Repository Structure

This repository is a monorepo containing two distinct and independent Python projects:

```
.
├── custom_xml_parser/   # Project 1: A parser for a custom XML-like format.
└── text_translator/     # Project 2: A command-line tool for translating text.
```

When working on a task, please identify which project it relates to and confine your changes to that project's directory.

## 2. Development Environment Setup

### 2.1. Python
This repository uses Python. Ensure you have a recent version of Python 3 installed.

### 2.2. Dependencies
Dependencies are managed on a per-project basis.

-   **`custom_xml_parser`**: This project has **no external dependencies**.
-   **`text_translator`**: This project's dependencies are listed in `text_translator/requirements.txt`. Install them with:
    ```bash
    pip install -r text_translator/requirements.txt
    ```

## 3. General Workflow

1.  **Understand the Goal**: Read the user's request carefully.
2.  **Identify the Project**: Determine if the task relates to `custom_xml_parser` or `text_translator`.
3.  **Implement Changes**: Make code changes within the relevant project directory.
4.  **Run Tests**: Use the testing instructions below to verify your changes. You **must** run the full verification script before submitting.
5.  **Submit**: Once all checks pass, submit your work following the commit guidelines.

## 4. Testing

### 4.1. Running All Tests (Mandatory before submission)
A verification script is provided to run all checks for the repository. This script installs dependencies and runs the test suites for both projects.

**Execute it from the repository root:**
```bash
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
```

### 4.2. Running Tests for a Single Project
To run tests for a specific project, use the following commands from the repository root:

-   **`custom_xml_parser`**:
    ```bash
    python -m unittest custom_xml_parser.tests.test_parser
    ```
-   **`text_translator`**:
    ```bash
    python -m unittest text_translator.tests.test_cli text_translator.tests.test_core
    ```

### 4.3. Running a Specific Test File or Class
You can run a specific test file or even a single test class for more focused testing:
```bash
# Example for a specific file
python -m unittest text_translator.tests.test_core

# Example for a specific class in a file
python -m unittest text_translator.tests.test_cli.TestCommandLineInterface
```

## 5. Code Style

Please follow the existing code style in the files you are editing.
-   Use clear and descriptive variable and function names.
-   Keep functions focused on a single responsibility.
-   Add comments to explain complex or non-obvious logic.

## 6. Commit & Submission Guidelines

When submitting your work, please follow these guidelines for the commit message:

-   **Format**: Use the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) format.
-   **Subject Line**: The subject line should be a concise summary of the change, prefixed with a type (e.g., `feat`, `fix`, `docs`, `refactor`).
    -   Example: `feat: Add new serialization option to XML parser`
    -   Example: `fix: Correctly handle empty tags in text translator`
    -   Example: `docs: Update AGENTS.md with testing instructions`
-   **Body**: The commit message body should provide more context, explaining the "what" and "why" of the change.

Thank you for your cooperation!
