"""Versioned prompt library for Signal North.

Prompts are core IP. Each prompt has a NAME and an integer VERSION and lives
as a plain-text file at ``prompts/<name>/v<N>.txt``. The active version for
each name is recorded in ``ACTIVE_VERSIONS`` below and stamped onto every
artifact the prompt produces (e.g. ``signals.extracted_by = "extraction@v1"``)
so every row is traceable to the exact prompt that generated it.

Rules:
- Never edit a released version in place. To change a prompt, add a new
  ``v<N+1>.txt``, bump ``ACTIVE_VERSIONS``, and record it in CHANGELOG.md.
- ``extracted_by`` uses the ``<name>@v<version>`` form, not a model id, so the
  provenance survives a model swap. The model id is recorded separately.
"""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent

# Active version per prompt name. Bump when a new version is released, and add
# a matching CHANGELOG.md entry in the same commit.
ACTIVE_VERSIONS = {
    "extraction": 2,
    "discovery": 1,
}


def prompt_stamp(name: str, version: int | None = None) -> str:
    """Provenance stamp for artifacts, e.g. ``"extraction@v1"``."""
    if version is None:
        version = ACTIVE_VERSIONS[name]
    return f"{name}@v{version}"


def get_prompt(name: str, version: int | None = None) -> tuple[str, str]:
    """Return ``(prompt_text, stamp)`` for a prompt.

    Defaults to the active version for ``name``. ``stamp`` is the value to
    record on produced artifacts (see ``prompt_stamp``).
    """
    if version is None:
        version = ACTIVE_VERSIONS[name]
    path = _PROMPTS_DIR / name / f"v{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"No prompt {name}@v{version} at {path}")
    return path.read_text(encoding="utf-8"), prompt_stamp(name, version)
