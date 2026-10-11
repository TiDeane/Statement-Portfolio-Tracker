"""Writing results somewhere the user keeps them. Excel first; others share the same interface."""

from statement_tracker.core.exporters.base import Exporter, ExportResult

__all__ = ["ExportResult", "Exporter"]
