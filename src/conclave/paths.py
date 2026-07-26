from pathlib import Path


def repository_root() -> Path:
    """Return the project root for local contracts and design fixtures."""
    return Path(__file__).resolve().parents[2]


def contracts_root() -> Path:
    return repository_root() / "hyperstructure-review-contracts"


def design_fixtures_root() -> Path:
    return repository_root() / "design-fixtures"
