"""The one error type of the case records: a plain-language message the user can act on, an HTTP status and a code."""
from __future__ import annotations


class RecordError(Exception):
    def __init__(self, message: str, status: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
