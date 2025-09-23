from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class TranslationOptions:
    """A data class to hold all settings for the translation process.

    This class centralizes all the configuration options that control the
    behavior of the translation script, from input/output paths to model
    parameters and API settings.

    Attributes:
        input_path: Path to the input file or directory.
        model_name: Name of the main translation model to use.
        output_path: Optional path for the output file or directory. If None,
            output is printed to stdout.
        api_base_url: The base URL for the LLM API server.
        glossary_text: A string containing glossary terms to guide translation.
        glossary_for: Specifies whether the glossary applies to 'draft',
            'refine', or 'all' models.
        refine_mode: If True, enables a two-step translation process where a
            draft model generates initial translations and a refine model
            improves them.
        draft_model: The name of the model to use for generating drafts in
            refine mode.
        num_drafts: The number of draft translations to generate in refine mode.
        reasoning_for: Enables step-by-step reasoning for the specified model
            type ('draft', 'refine', 'main', or 'all').
        line_by_line: If True, processes files line by line instead of as a
            single block of text.
        overwrite: If True, allows overwriting existing output files.
        verbose: If True, enables detailed status messages (e.g., model loading).
        quiet: If True, suppresses all non-essential output.
        debug: If True, enables extensive debug logging for troubleshooting.
        model_config: A dictionary holding the loaded configuration for the
            main model, including prompts and API parameters.
        draft_model_config: A dictionary holding the loaded configuration for
            the draft model.
    """
    input_path: str
    model_name: str
    output_path: Optional[str] = None
    api_base_url: str = "http://127.0.0.1:5000/v1"
    glossary_text: Optional[str] = None
    glossary_for: Optional[str] = None
    refine_mode: bool = False
    draft_model: Optional[str] = None
    num_drafts: int = 6
    reasoning_for: Optional[str] = None
    line_by_line: bool = False
    overwrite: bool = False
    verbose: bool = False
    quiet: bool = False
    debug: bool = False
    model_config: Dict[str, Any] = field(default_factory=dict)
    draft_model_config: Dict[str, Any] = field(default_factory=dict)
