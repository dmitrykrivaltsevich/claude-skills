# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Design by Contract (DbC) decorators.

Provides @precondition, @postcondition, and @invariant decorators
that enforce contracts at runtime, raising ContractViolationError
on violation.

Also provides check_file_readable() for TCC-aware file access validation.
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable


# macOS TCC-protected directories where terminal processes are often blocked.
_TCC_DIRS = ("Desktop", "Documents", "Downloads")


def check_file_readable(path: str) -> bool:
    """Verify a file exists AND is readable by the current process.

    On macOS, files in ~/Desktop, ~/Documents, etc. may exist but be
    blocked by TCC (Transparency, Consent, Control). os.path.isfile()
    returns True for such files, but open() raises PermissionError.

    Raises ContractViolationError with an actionable message instead of
    returning False, so the user/LLM knows exactly what to do.
    """
    if not os.path.isfile(path):
        raise ContractViolationError(
            f"File does not exist: {path}",
            kind="precondition",
        )

    try:
        with open(path, "rb") as f:
            f.read(1)
    except PermissionError:
        abs_path = os.path.abspath(path)
        home = os.path.expanduser("~")
        # Detect if the file is in a TCC-protected directory
        rel = os.path.relpath(abs_path, home) if abs_path.startswith(home) else ""
        top_dir = rel.split(os.sep)[0] if rel else ""

        if top_dir in _TCC_DIRS:
            raise ContractViolationError(
                f"macOS blocked access to '{abs_path}'. "
                f"The ~/{top_dir} folder is protected by macOS privacy settings (TCC). "
                f"Fix: copy the file to a non-protected location first:\n"
                f"  open -R \"{abs_path}\"  # reveals in Finder\n"
                f"Then drag-copy it to ~/Downloads or /tmp, and use the new path.",
                kind="precondition",
            )
        raise ContractViolationError(
            f"Permission denied reading '{abs_path}'. Check file permissions.",
            kind="precondition",
        )

    return True


class ContractViolationError(Exception):
    """Raised when a contract (precondition, postcondition, or invariant) is violated."""

    def __init__(self, message: str, kind: str = "contract") -> None:
        super().__init__(message)
        self.kind = kind


def precondition(
    check: Callable[..., bool], message: str
) -> Callable:
    """Decorator that validates function arguments before execution.

    The check function receives the same arguments as the decorated function.
    If it returns False, ContractViolationError is raised.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            if not check(**bound.arguments):
                raise ContractViolationError(message, kind="precondition")
            return func(*args, **kwargs)

        return wrapper

    return decorator


def postcondition(
    check: Callable[[Any], bool], message: str
) -> Callable:
    """Decorator that validates the return value after execution.

    The check function receives the return value as its sole argument.
    If it returns False, ContractViolationError is raised.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            if not check(result):
                raise ContractViolationError(message, kind="postcondition")
            return result

        return wrapper

    return decorator


def invariant(
    check: Callable[[Any], bool], message: str
) -> Callable:
    """Decorator for methods that validates an object invariant after execution.

    The check function receives `self` (the first argument) after the method
    has executed. If it returns False, ContractViolationError is raised.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self_arg: Any, *args: Any, **kwargs: Any) -> Any:
            result = func(self_arg, *args, **kwargs)
            if not check(self_arg):
                raise ContractViolationError(message, kind="invariant")
            return result

        return wrapper

    return decorator
