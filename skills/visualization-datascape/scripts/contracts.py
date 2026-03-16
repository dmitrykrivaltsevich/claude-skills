# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Design by Contract (DbC) decorators.

Provides @precondition, @postcondition, and @invariant decorators
that enforce contracts at runtime, raising ContractViolationError
on violation.
"""
from __future__ import annotations

import functools
from typing import Any, Callable


class ContractViolationError(Exception):
    """Raised when a contract (precondition, postcondition, or invariant) is violated."""

    def __init__(self, message: str, kind: str = "contract") -> None:
        super().__init__(message)
        self.kind = kind


def precondition(
    check: Callable[..., bool], message: str
) -> Callable:
    """Decorator that validates function arguments before execution."""

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
    """Decorator that validates the return value after execution."""

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
