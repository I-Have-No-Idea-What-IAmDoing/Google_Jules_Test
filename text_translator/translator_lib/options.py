from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class TranslationOptions:
    """
    A data class to hold all the options for the translation process.
    """
    input_path: str
    model_name: str
    output_path: Optional[str] = None
    api_base_url: str = "http://127.0.0.1:5000/v1"
    glossary_text: Optional[str] = None
    glossary_for: str = 'all'
    refine_mode: bool = False
    draft_model: Optional[str] = None
    num_drafts: int = 6
    reasoning_for: Optional[str] = None
    line_by_line: bool = False
    overwrite: bool = False
    verbose: bool = False
    quiet: bool = False
    debug: bool = False
    # New fields for model configurations
    model_config: Dict[str, Any] = field(default_factory=dict)
    draft_model_config: Dict[str, Any] = field(default_factory=dict)
