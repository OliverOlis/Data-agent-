from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    aliases: tuple[str, ...]
    definition: str
    formula: str
    grain: str
    allowed_dimensions: tuple[str, ...]
    time_field: str
    filters: tuple[str, ...] = ()
    denominator: str | None = None
    null_policy: str = "return_null"
    owner: str = "data-ops"
    status: str = "published"
    version: str = "v1"
    examples: tuple[str, ...] = ()


@dataclass(frozen=True)
class DimensionDefinition:
    name: str
    source: str
    data_type: str
    aliases: tuple[str, ...] = ()


@dataclass
class SemanticRegistry:
    metrics: dict[str, MetricDefinition] = field(default_factory=dict)
    dimensions: dict[str, DimensionDefinition] = field(default_factory=dict)
    version: str = "semantic-v1"

    @classmethod
    def default(cls) -> "SemanticRegistry":
        path = Path(__file__).with_name("definitions.json")
        return cls.from_json(path)

    @classmethod
    def from_json(cls, path: str | Path) -> "SemanticRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        metrics = {m["name"]: MetricDefinition(
            name=m["name"], aliases=tuple(m.get("aliases", [])), definition=m["definition"],
            formula=m["formula"], grain=m.get("grain", "event"),
            allowed_dimensions=tuple(m.get("allowed_dimensions", [])), time_field=m["time_field"],
            filters=tuple(m.get("filters", [])), denominator=m.get("denominator"),
            null_policy=m.get("null_policy", "return_null"), owner=m.get("owner", "data-ops"),
            status=m.get("status", "published"), version=m.get("version", data.get("version", "v1")),
            examples=tuple(m.get("examples", []))) for m in data.get("metrics", [])}
        dims = {d["name"]: DimensionDefinition(d["name"], d["source"], d.get("data_type", "text"), tuple(d.get("aliases", []))) for d in data.get("dimensions", [])}
        return cls(metrics=metrics, dimensions=dims, version=data.get("version", "semantic-v1"))

    def resolve_metric(self, term: str) -> MetricDefinition | None:
        needle = term.strip().lower()
        for metric in self.metrics.values():
            if needle == metric.name.lower() or needle in {a.lower() for a in metric.aliases}:
                return metric
        return None

    def search_metrics(self, terms: Iterable[str]) -> list[MetricDefinition]:
        return [m for m in self.metrics.values() if any(self.resolve_metric(t) is m for t in terms)]

    def to_context(self) -> dict[str, Any]:
        """Return a JSON-serializable, model-safe semantic context."""
        return {"version": self.version, "metrics": [m.__dict__ for m in self.metrics.values()], "dimensions": [d.__dict__ for d in self.dimensions.values()]}
