# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Tests for Design by Contract decorators."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import (
    ContractViolationError,
    precondition,
    postcondition,
    invariant,
)


class TestContractViolationError:
    def test_is_exception(self):
        assert issubclass(ContractViolationError, Exception)

    def test_stores_message(self):
        err = ContractViolationError("bad input")
        assert str(err) == "bad input"

    def test_stores_kind(self):
        err = ContractViolationError("msg", kind="precondition")
        assert err.kind == "precondition"


class TestPrecondition:
    def test_passes_when_check_returns_true(self):
        @precondition(lambda x: x > 0, "x must be positive")
        def double(x):
            return x * 2

        assert double(5) == 10

    def test_raises_when_check_returns_false(self):
        @precondition(lambda x: x > 0, "x must be positive")
        def double(x):
            return x * 2

        with pytest.raises(ContractViolationError, match="x must be positive"):
            double(-1)

    def test_error_kind_is_precondition(self):
        @precondition(lambda x: x > 0, "positive")
        def f(x):
            return x

        with pytest.raises(ContractViolationError) as exc_info:
            f(0)
        assert exc_info.value.kind == "precondition"

    def test_multiple_preconditions(self):
        @precondition(lambda x, y: x > 0, "x must be positive")
        @precondition(lambda x, y: y > 0, "y must be positive")
        def add(x, y):
            return x + y

        assert add(1, 2) == 3
        with pytest.raises(ContractViolationError, match="y must be positive"):
            add(1, -1)
        with pytest.raises(ContractViolationError, match="x must be positive"):
            add(-1, 1)

    def test_works_with_kwargs(self):
        @precondition(lambda name: name and name.strip(), "name must be non-empty")
        def greet(name):
            return f"Hello, {name}"

        assert greet(name="Alice") == "Hello, Alice"
        with pytest.raises(ContractViolationError):
            greet(name="")

    def test_check_receives_all_args(self):
        received = {}

        def check(a, b, c=None):
            received.update({"a": a, "b": b, "c": c})
            return True

        @precondition(check, "msg")
        def f(a, b, c=None):
            pass

        f(1, 2, c=3)
        assert received == {"a": 1, "b": 2, "c": 3}


class TestPostcondition:
    def test_passes_when_check_returns_true(self):
        @postcondition(lambda result: result > 0, "result must be positive")
        def double(x):
            return x * 2

        assert double(5) == 10

    def test_raises_when_check_returns_false(self):
        @postcondition(lambda result: result > 0, "result must be positive")
        def negate(x):
            return -x

        with pytest.raises(ContractViolationError, match="result must be positive"):
            negate(5)

    def test_error_kind_is_postcondition(self):
        @postcondition(lambda result: result is not None, "not none")
        def f():
            return None

        with pytest.raises(ContractViolationError) as exc_info:
            f()
        assert exc_info.value.kind == "postcondition"

    def test_result_is_returned_on_success(self):
        @postcondition(lambda result: isinstance(result, dict), "must be dict")
        def make_dict():
            return {"key": "value"}

        assert make_dict() == {"key": "value"}


class TestInvariant:
    def test_passes_when_check_returns_true(self):
        class Counter:
            def __init__(self):
                self.count = 0

            @invariant(lambda self: self.count >= 0, "count must be non-negative")
            def increment(self):
                self.count += 1
                return self.count

        c = Counter()
        assert c.increment() == 1

    def test_raises_when_check_fails_after_call(self):
        class Counter:
            def __init__(self):
                self.count = 0

            @invariant(lambda self: self.count >= 0, "count must be non-negative")
            def decrement(self):
                self.count -= 1
                return self.count

        c = Counter()
        with pytest.raises(ContractViolationError, match="count must be non-negative"):
            c.decrement()

    def test_error_kind_is_invariant(self):
        class Obj:
            def __init__(self):
                self.valid = True

            @invariant(lambda self: self.valid, "must be valid")
            def invalidate(self):
                self.valid = False

        with pytest.raises(ContractViolationError) as exc_info:
            Obj().invalidate()
        assert exc_info.value.kind == "invariant"


class TestCombinedContracts:
    def test_precondition_and_postcondition_together(self):
        @precondition(lambda x: x >= 0, "x must be non-negative")
        @postcondition(lambda result: result >= 0, "result must be non-negative")
        def sqrt_approx(x):
            return x ** 0.5

        assert sqrt_approx(4) == 2.0
        with pytest.raises(ContractViolationError, match="x must be non-negative"):
            sqrt_approx(-1)
