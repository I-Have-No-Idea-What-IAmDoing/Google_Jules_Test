from setuptools import setup, find_packages

setup(
    name="text_translator_project",
    version="1.1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'text-translator=text_translator.cli:main',
        ],
    },
    install_requires=[
        "requests",
        "tqdm",
        "langdetect",
    ],
)
