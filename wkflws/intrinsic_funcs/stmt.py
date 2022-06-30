"""Statement definitions for the intrinsic function interpreter.

BNF:
program   -> statement* EOF ;
statement -> exprStmt ;
exprStmt  -> expression ;
"""
import abc
from dataclasses import dataclass
from typing import Generic, TypeVar

from .expr import Expr

T = TypeVar("T")


class Visitor(Generic[T], abc.ABC):
    @abc.abstractmethod
    def visit_expression_stmt(self, expr: "Expression") -> T:
        pass


class Stmt(abc.ABC):
    @abc.abstractmethod
    def accept(self, visitor: Visitor[T]) -> T:
        pass


@dataclass
class Expression(Stmt):
    expression: Expr

    def accept(self, visitor: Visitor[T]) -> T:
        return visitor.visit_expression_stmt(self)
