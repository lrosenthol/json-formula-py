"""Pratt parser for JSON Formula expressions."""

from __future__ import annotations

from typing import Any

from ._errors import syntax_error
from .lexer import Lexer
from .tokens import *


BINDING_POWER = {
    TOK_EOF: 0,
    TOK_IDENTIFIER: 0,
    TOK_QUOTEDIDENTIFIER: 0,
    TOK_RBRACKET: 0,
    TOK_RPAREN: 0,
    TOK_COMMA: 0,
    TOK_RBRACE: 0,
    TOK_NUMBER: 0,
    TOK_INT: 0,
    TOK_CURRENT: 0,
    TOK_GLOBAL: 0,
    TOK_EXPREF: 0,
    TOK_PIPE: 1,
    TOK_OR: 2,
    TOK_AND: 3,
    TOK_COMPARATOR: 4,
    TOK_CONCATENATE: 5,
    TOK_ADD: 6,
    TOK_SUBTRACT: 6,
    TOK_UNION: 6,
    TOK_MULTIPLY: 7,
    TOK_DIVIDE: 7,
    TOK_NOT: 8,
    TOK_UNARY_MINUS: 8,
    TOK_FLATTEN: 10,
    TOK_STAR: 20,
    TOK_FILTER: 21,
    TOK_DOT: 40,
    TOK_LBRACE: 50,
    TOK_LBRACKET: 55,
    TOK_LPAREN: 60,
}


class Parser:
    def __init__(self, allowed_global_names: list[str] | None = None) -> None:
        self.allowed_global_names = allowed_global_names or []
        self.debug: list[str] = []
        self.tokens: list[dict[str, Any]] = []
        self.index = 0

    def parse(self, expression: str, debug: list[str] | None = None) -> dict[str, Any]:
        self.debug = debug if debug is not None else []
        lexer = Lexer(self.allowed_global_names, self.debug)
        self.tokens = lexer.tokenize(expression)
        self.tokens.append({"type": TOK_EOF, "value": "", "start": len(expression)})
        self.index = 0
        ast = self.expression(0)
        if self._lookahead(0) != TOK_EOF:
            token = self._lookahead_token(0)
            raise syntax_error(f"Unexpected token type: {token['type']}, value: {token.get('value')}")
        return ast

    def expression(self, rbp: int) -> dict[str, Any]:
        left_token = self._lookahead_token(0)
        self._advance()
        left = self.nud(left_token)
        current = self._lookahead_token(0, left)
        while rbp < BINDING_POWER[current["type"]]:
            self._advance()
            left = self.led(current, left)
            current = self._lookahead_token(0, left)
        return left

    def _lookahead(self, number: int) -> str:
        return self.tokens[self.index + number]["type"]

    def _lookahead_token(self, number: int, previous: dict[str, Any] | None = None) -> dict[str, Any]:
        next_token = dict(self.tokens[self.index + number])
        previous_type = None if previous is None else previous.get("type")
        if next_token["type"] == TOK_STAR and previous_type not in {
            None,
            TOK_LBRACKET,
            TOK_DOT,
            TOK_PIPE,
            TOK_AND,
            TOK_OR,
            TOK_COMMA,
            TOK_NOT,
            TOK_MULTIPLY,
            TOK_ADD,
            TOK_SUBTRACT,
            TOK_DIVIDE,
            TOK_LPAREN,
            TOK_CONCATENATE,
            TOK_UNION,
            TOK_COMPARATOR,
        }:
            next_token["type"] = TOK_MULTIPLY
        return next_token

    def _advance(self) -> None:
        self.index += 1

    def _look_ahead_index(self) -> bool:
        idx = 0
        if self._lookahead(idx) == TOK_UNARY_MINUS:
            idx += 1
        if self._lookahead(idx) == TOK_INT:
            idx += 1
        return self._lookahead(idx) in {TOK_RBRACKET, TOK_COLON}

    def nud(self, token: dict[str, Any]) -> dict[str, Any]:
        token_type = token["type"]
        if token_type == TOK_STRING:
            return {"type": "String", "value": token["value"]}
        if token_type == TOK_JSON:
            return {"type": "Literal", "value": token["value"]}
        if token_type == TOK_NUMBER:
            return {"type": "Number", "value": token["value"]}
        if token_type == TOK_INT:
            return {"type": "Integer", "value": token["value"]}
        if token_type == TOK_IDENTIFIER:
            return {"type": "Identifier", "name": token["value"]}
        if token_type == TOK_QUOTEDIDENTIFIER:
            return {"type": "QuotedIdentifier", "name": token["value"]}
        if token_type == TOK_NOT:
            return {"type": "NotExpression", "children": [self.expression(BINDING_POWER[TOK_NOT])]}
        if token_type == TOK_UNARY_MINUS:
            return {"type": "UnaryMinusExpression", "children": [self.expression(BINDING_POWER[TOK_UNARY_MINUS])]}
        if token_type == TOK_STAR:
            left = {"type": "Identity"}
            right = {"type": "Identity"} if self._lookahead(0) == TOK_RBRACKET else self._parse_projection_rhs(BINDING_POWER[TOK_STAR])
            return {"type": "ValueProjection", "children": [left, right]}
        if token_type == TOK_FILTER:
            return self.led(token, {"type": "Identity"})
        if token_type == TOK_LBRACE:
            return self._parse_object_expression()
        if token_type == TOK_FLATTEN:
            left = {"type": TOK_FLATTEN, "children": [{"type": "Identity"}]}
            right = self._parse_projection_rhs(BINDING_POWER[TOK_FLATTEN])
            return {"type": "Projection", "children": [left, right]}
        if token_type == TOK_LBRACKET:
            if self._look_ahead_index():
                right = self._parse_index_expression()
                return self._project_if_slice({"type": "Identity"}, right)
            if self._lookahead(0) == TOK_STAR and self._lookahead(1) == TOK_RBRACKET:
                self._advance()
                self._advance()
                right = self._parse_projection_rhs(BINDING_POWER[TOK_STAR])
                return {"type": "Projection", "children": [{"type": "Identity"}, right], "debug": "Wildcard"}
            return self._parse_array_expression()
        if token_type == TOK_CURRENT:
            return {"type": TOK_CURRENT}
        if token_type == TOK_GLOBAL:
            return {"type": TOK_GLOBAL, "name": token["name"]}
        if token_type == TOK_EXPREF:
            return {"type": "ExpressionReference", "children": [self.expression(BINDING_POWER[TOK_EXPREF])]}
        if token_type == TOK_LPAREN:
            args: list[dict[str, Any]] = []
            while self._lookahead(0) != TOK_RPAREN:
                args.append(self.expression(0))
            self._match(TOK_RPAREN)
            return args[0]
        raise syntax_error(f'Unexpected token ({token_type}): "{token.get("value", token.get("name"))}"')

    def led(self, token: dict[str, Any], left: dict[str, Any]) -> dict[str, Any]:
        token_name = token["type"]
        if token_name == TOK_CONCATENATE:
            return {"type": "ConcatenateExpression", "children": [left, self.expression(BINDING_POWER[TOK_CONCATENATE])]}
        if token_name == TOK_DOT:
            if self._lookahead(0) != TOK_STAR:
                return {"type": "ChainedExpression", "children": [left, self._parse_dot_rhs(BINDING_POWER[TOK_DOT])]}
            self._advance()
            return {"type": "ValueProjection", "children": [left, self._parse_projection_rhs(BINDING_POWER[TOK_DOT])]}
        if token_name == TOK_PIPE:
            return {"type": TOK_PIPE, "children": [left, self.expression(BINDING_POWER[TOK_PIPE])]}
        if token_name == TOK_OR:
            return {"type": "OrExpression", "children": [left, self.expression(BINDING_POWER[TOK_OR])]}
        if token_name == TOK_AND:
            return {"type": "AndExpression", "children": [left, self.expression(BINDING_POWER[TOK_AND])]}
        if token_name == TOK_ADD:
            return {"type": "AddExpression", "children": [left, self.expression(BINDING_POWER[TOK_ADD])]}
        if token_name == TOK_SUBTRACT:
            return {"type": "SubtractExpression", "children": [left, self.expression(BINDING_POWER[TOK_SUBTRACT])]}
        if token_name == TOK_MULTIPLY:
            return {"type": "MultiplyExpression", "children": [left, self.expression(BINDING_POWER[TOK_MULTIPLY])]}
        if token_name == TOK_DIVIDE:
            return {"type": "DivideExpression", "children": [left, self.expression(BINDING_POWER[TOK_DIVIDE])]}
        if token_name == TOK_UNION:
            return {"type": "UnionExpression", "children": [left, self.expression(BINDING_POWER[TOK_UNION])]}
        if token_name == TOK_LPAREN:
            if left["type"] != TOK_IDENTIFIER:
                raise syntax_error("Bad function syntax. Parenthesis must be preceded by an unquoted identifier")
            return {"type": "Function", "name": left["name"], "children": self._parse_function_args()}
        if token_name == TOK_FILTER:
            condition = self.expression(0)
            self._match(TOK_RBRACKET)
            return {
                "type": "FilterProjection",
                "children": [left, self._parse_projection_rhs(BINDING_POWER[TOK_FILTER]), condition],
            }
        if token_name == TOK_FLATTEN:
            left_node = {"type": TOK_FLATTEN, "children": [left]}
            return {"type": "Projection", "children": [left_node, self._parse_projection_rhs(BINDING_POWER[TOK_FLATTEN])]}
        if token_name == TOK_COMPARATOR:
            return {"type": "Comparator", "value": token["value"], "children": [left, self.expression(BINDING_POWER[TOK_COMPARATOR])]}
        if token_name == TOK_LBRACKET:
            if self._lookahead(0) == TOK_STAR and self._lookahead(1) == TOK_RBRACKET:
                self._advance()
                self._advance()
                return {
                    "type": "Projection",
                    "children": [left, self._parse_projection_rhs(BINDING_POWER[TOK_STAR])],
                    "debug": "Wildcard",
                }
            right = self._parse_index_expression()
            return self._project_if_slice(left, right)
        raise syntax_error(f'Unexpected token ({token_name}): "{token.get("value", token.get("name"))}"')

    def _match(self, token_type: str) -> dict[str, Any]:
        token = self._lookahead_token(0)
        if token["type"] == token_type:
            self._advance()
            return token
        raise syntax_error(f"Expected {token_type}, got: {token['type']}")

    def _parse_function_args(self) -> list[dict[str, Any]]:
        first = True
        args: list[dict[str, Any]] = []
        while self._lookahead(0) != TOK_RPAREN:
            if not first:
                self._match(TOK_COMMA)
            args.append(self.expression(0))
            first = False
        self._match(TOK_RPAREN)
        return args

    def _parse_signed_int(self) -> dict[str, Any]:
        first = self._lookahead_token(0)
        if first["type"] == TOK_UNARY_MINUS:
            self._advance()
            value = self._match(TOK_INT)
            return {"type": "SignedInt", "value": -value["value"]}
        if first["type"] != TOK_INT:
            raise syntax_error(f'Unexpected token ({first["type"]}): "{first.get("value", first.get("name"))}"')
        self._advance()
        return {"type": "SignedInt", "value": first["value"]}

    def _parse_index_expression(self) -> dict[str, Any]:
        old_index = self.index
        if self._lookahead(0) == TOK_COLON:
            return self._parse_slice_expression()
        first = self._parse_signed_int()
        if self._lookahead(0) == TOK_COLON:
            self.index = old_index
            return self._parse_slice_expression()
        self._match(TOK_RBRACKET)
        return {"type": "Index", "value": first}

    def _project_if_slice(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        index_expr = {"type": "BracketExpression", "children": [left, right]}
        if right["type"] == "Slice":
            return {"type": "Projection", "children": [index_expr, self._parse_projection_rhs(BINDING_POWER[TOK_STAR])]}
        return index_expr

    def _parse_slice_expression(self) -> dict[str, Any]:
        parts: list[dict[str, Any] | None] = [None, None, None]
        index = 0
        current = self._lookahead(0)
        while current != TOK_RBRACKET and index < 3:
            if current == TOK_COLON and index < 2:
                index += 1
                self._advance()
            else:
                parts[index] = self._parse_signed_int()
                token = self._lookahead(0)
                if token not in {TOK_COLON, TOK_RBRACKET}:
                    raise syntax_error(f"Unexpected token: {self._lookahead_token(0).get('value')}({token})")
            current = self._lookahead(0)
        self._match(TOK_RBRACKET)
        return {"type": "Slice", "children": parts}

    def _parse_dot_rhs(self, rbp: int) -> dict[str, Any]:
        lookahead = self._lookahead(0)
        if lookahead in {TOK_IDENTIFIER, TOK_QUOTEDIDENTIFIER, TOK_STAR}:
            return self.expression(rbp)
        if lookahead == TOK_LBRACKET:
            self._match(TOK_LBRACKET)
            return self._parse_array_expression()
        if lookahead == TOK_LBRACE:
            self._match(TOK_LBRACE)
            return self._parse_object_expression()
        raise syntax_error('Expecting one of: "*", "[", "{", name or quoted name after a dot')

    def _parse_projection_rhs(self, rbp: int) -> dict[str, Any]:
        next_token = self._lookahead_token(0, {"type": TOK_STAR})
        if BINDING_POWER[next_token["type"]] <= BINDING_POWER[TOK_FLATTEN]:
            return {"type": "Identity"}
        if next_token["type"] in {TOK_LBRACKET, TOK_FILTER}:
            return self.expression(rbp)
        if next_token["type"] == TOK_DOT:
            self._match(TOK_DOT)
            return self._parse_dot_rhs(rbp)
        raise syntax_error(f"Unexpected token: {next_token.get('value')}({next_token['type']})")

    def _parse_array_expression(self) -> dict[str, Any]:
        expressions: list[dict[str, Any]] = []
        while self._lookahead(0) != TOK_RBRACKET:
            expressions.append(self.expression(0))
            if self._lookahead(0) == TOK_COMMA:
                self._match(TOK_COMMA)
                if self._lookahead(0) == TOK_RBRACKET:
                    raise syntax_error("Unexpected token Rbracket")
        self._match(TOK_RBRACKET)
        return {"type": "ArrayExpression", "children": expressions}

    def _parse_object_expression(self) -> dict[str, Any]:
        pairs: list[dict[str, Any]] = []
        if self._lookahead(0) == TOK_RBRACE:
            self.debug.append("To create an empty object, use a JSON literal: `{}`")
            raise syntax_error("An empty object expression is not allowed")
        while True:
            key_token = self._lookahead_token(0)
            if key_token["type"] not in {TOK_IDENTIFIER, TOK_QUOTEDIDENTIFIER}:
                raise syntax_error(f"Expecting an identifier token, got: {key_token['type']}")
            key_name = key_token["value"]
            self._advance()
            self._match(TOK_COLON)
            pairs.append({"type": "KeyValuePair", "name": key_name, "value": self.expression(0)})
            if self._lookahead(0) == TOK_COMMA:
                self._match(TOK_COMMA)
            elif self._lookahead(0) == TOK_RBRACE:
                self._match(TOK_RBRACE)
                break
        return {"type": "ObjectExpression", "children": pairs}
