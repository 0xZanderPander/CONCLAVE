import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for
from pydantic import BaseModel

from conclave.paths import repository_root
from conclave.pilot.phase8 import PHASE8_ARTIFACT_MODELS


@dataclass(frozen=True, slots=True)
class Phase8SchemaExport:
    artifact_count: int
    output_dir: Path


def phase8_contracts_root() -> Path:
    return repository_root() / "phase8-contracts"


def phase8_schemas_root() -> Path:
    return phase8_contracts_root() / "schemas"


def phase8_json_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for name, model in PHASE8_ARTIFACT_MODELS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://conclave.local/contracts/phase8/{name}.v1.schema.json"
        schemas[name] = schema
    return schemas


def write_phase8_json_schemas(output_dir: Path | None = None) -> Phase8SchemaExport:
    output_dir = output_dir or phase8_schemas_root()
    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = phase8_json_schemas()
    for name, schema in schemas.items():
        path = output_dir / f"{name}.v1.schema.json"
        path.write_text(
            json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return Phase8SchemaExport(artifact_count=len(schemas), output_dir=output_dir)


def validate_phase8_artifact(
    artifact_name: str,
    document: dict[str, Any],
) -> BaseModel:
    try:
        model = PHASE8_ARTIFACT_MODELS[artifact_name]
    except KeyError as exc:
        raise ValueError(f"unknown Phase 8 artifact contract {artifact_name!r}") from exc
    return model.model_validate(document)


def validate_committed_phase8_schemas() -> None:
    expected = phase8_json_schemas()
    root = phase8_schemas_root()
    actual_paths = sorted(root.glob("*.schema.json"))
    expected_names = {f"{name}.v1.schema.json" for name in expected}
    if {path.name for path in actual_paths} != expected_names:
        raise ValueError("committed Phase 8 schema set does not match the model registry")
    for name, schema in expected.items():
        path = root / f"{name}.v1.schema.json"
        committed = json.loads(path.read_text(encoding="utf-8"))
        if committed != schema:
            raise ValueError(f"committed schema is stale: {path.name}")
        validator = validator_for(committed)
        validator.check_schema(committed)
