"""
User Interface module.

This package contains UI implementations for displaying counseling results.
Currently implements terminal/console output.

To add a new UI (e.g., web, PDF), create a new module in this package
with the same method signatures as TerminalDisplay.
"""

from .terminal import TerminalDisplay

__all__ = ["TerminalDisplay"]

