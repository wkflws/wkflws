"""Expression definitions for the intrinsic function parser.

BNF:
expression   -> literal | unary | binary | grouping ;
literal      -> NUMBER | STRING ;
variable     ->
grouping     -> "(" expression ")" ;
unary        -> "-" expression ;
binary       -> expression operator expression ;
operator     -> "+" | "-" | "*" | "/" ;
"""
import abc
from dataclasses import dataclass
from typing import Any, Generic, List, TypeVar

from .token import Token


T = TypeVar("T")


class Visitor(Generic[T], abc.ABC):
    """Base class for defining an expression visitor."""

    # The methods are stubbed here for type checking.
    @abc.abstractmethod
    def visit_binary_expr(self, expr: "Binary") -> T:  # noqa: D102 docstring
        pass

    @abc.abstractmethod
    def visit_grouping_expr(self, expr: "Grouping") -> T:  # noqa: D102 docstring
        pass

    @abc.abstractmethod
    def visit_literal_expr(self, expr: "Literal") -> T:  # noqa: D102 docstring
        pass

    @abc.abstractmethod
    def visit_variable_expr(self, expr: "Variable") -> T:  # noqa: D102 docstring
        pass

    @abc.abstractmethod
    def visit_unary_expr(self, expr: "Unary") -> T:  # noqa: D102 docstring
        pass

    @abc.abstractmethod
    def visit_call_expr(self, expr: "Call") -> T:  # noqa: D102 docstring
        pass


class Expr(abc.ABC):
    """Base class for describing expressions."""

    @abc.abstractmethod
    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        pass


@dataclass
class Binary(Expr):
    """Binary expressions include infix arithmetic (+, -, *, /).

    I'm not sure if Amazon's implementation supports arithmetic in functions but this
    could be useful. For example imagine a call like the following to display the amount
    a 10% discount code could save someone:

    ``States.Format('Your discount code could save you ${}', $.total_cost * 0.1)``

    Note: This could also include comparison operators (==, !=, <, etc).
    """

    left: Expr
    operator: Token
    right: Expr

    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        return visitor.visit_binary_expr(self)


@dataclass
class Literal(Expr):
    """Literal numbers and strings.

    Note: This could also include boolean and ``nil`` values.
    """

    value: Any

    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        return visitor.visit_literal_expr(self)


@dataclass
class Variable(Expr):
    """Variable identifiers."""

    name: Token

    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        return visitor.visit_variable_expr(self)


@dataclass
class Unary(Expr):
    """An expression with a prefix (such as - to negate a number).

    Note: This could also include the not operator (!).
    """

    operator: Token
    right: Expr

    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        return visitor.visit_unary_expr(self)


@dataclass
class Grouping(Expr):
    """Represents a pair of "(" and ")" wrapped around an expression."""

    expression: Expr

    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        return visitor.visit_grouping_expr(self)


@dataclass
class Call(Expr):
    """Represents a function call."""

    callee: Expr
    paren: Token
    arguments: List[Expr]

    def accept(self, visitor: Visitor[T]) -> T:  # noqa: D102 docstring
        return visitor.visit_call_expr(self)
