from decimal import Decimal
from typing import Any, Dict, List, Optional

from . import expr as _expr
from . import funcs  # noqa: Imported to register functions
from . import stmt as _stmt
from .environment import Environment
from .intrinsic_callable import IntrinsicCallable
from .tokentype import TokenType

# Our runtime error class shadows the built-in RuntimeError exception.
BuiltinRuntimeError = RuntimeError  # type: ignore
from .exceptions import RuntimeError  # noqa


class Interpreter(_expr.Visitor[Any], _stmt.Visitor[None]):
    def __init__(
        self,
        *,
        func_input_json: Optional[Dict[str, Any]] = None,
        context_json: Optional[Dict[str, Any]] = None,
    ):
        self.environment = Environment(
            func_input_json=func_input_json,
            context_json=context_json,
        )

    def interpret(self, statements: List[_stmt.Stmt]):
        for statement in statements:
            self.execute(statement)

    def execute(self, stmt: _stmt.Stmt):
        stmt.accept(self)

    def visit_expression_stmt(self, stmt: _stmt.Expression):
        self.evaluate(stmt.expression)

    def evaluate(self, expr: _expr.Expr) -> Any:
        return expr.accept(self)

    def visit_literal_expr(self, expr: _expr.Literal) -> Any:
        """Interprets a Literal to the preloaded value.

        Args:
            expr: The expression Literal.

        Returns:
            The Literal's value.
        """
        return expr.value

    def visit_grouping_expr(self, expr: _expr.Grouping) -> Any:
        return self.evaluate(expr.expression)

    def visit_unary_expr(self, expr: _expr.Unary) -> Any:
        value = self.evaluate(expr.right)

        if expr.operator.type == TokenType.MINUS:
            if not isinstance(value, Decimal):
                raise RuntimeError(expr.operator, "Operand must be a number.")
            return Decimal("-1.0") * value
        # else if: other types (e.g. !/not)

        return None  # Unreachable

    def visit_binary_expr(self, expr: _expr.Binary) -> Any:
        left = self.evaluate(expr.left)
        right = self.evaluate(expr.right)

        op = expr.operator.type
        match op:
            case TokenType.MINUS:
                return left - right
            case TokenType.SLASH:
                return left / right
            case TokenType.STAR:
                return left * right
            case TokenType.PLUS:
                # Assuming the types match, hand off the processing to Python.
                # It will correctly sum numbers (and bool) and concatenate strings.
                # Otherwise you would want to do if isinstance(expr.left.value, Decimal)
                # comparisons.
                #
                # Note: type() == type() gives a `use isinstance` warning so that's the
                # reason for this strange looking statement.
                if isinstance(left, type(right)):
                    return left + right

                raise RuntimeError(
                    expr.operator, "Operands must be two numbers or two strings."
                )

        return None  # Unreachable

    def visit_variable_expr(self, expr: _expr.Variable) -> Any:
        """Look up the value stored for a variable expression."""
        return self.environment.get(expr.name)

    def visit_call_expr(self, expr: _expr.Call) -> Any:
        """Evaluate an intrinsic call expression."""
        # This type hint is for editors so the auto-complete works.
        callee: IntrinsicCallable = self.evaluate(expr.callee)
        arguments = []
        for arg in expr.arguments:
            arguments.append(self.evaluate(arg))

        if callee.arity() is not None and len(arguments) != callee.arity():
            raise RuntimeError(
                expr.paren,
                f"Expected {callee.arity()} arguments but got {len(arguments)}.",
            )

        return callee.call(self, arguments)
