"""Lexer for JSON Formula expressions."""

from __future__ import annotations

import json
import re
from typing import Any

from ._errors import syntax_error
from .tokens import (
    TOK_ADD,
    TOK_AND,
    TOK_COLON,
    TOK_COMMA,
    TOK_COMPARATOR,
    TOK_CONCATENATE,
    TOK_CURRENT,
    TOK_DIVIDE,
    TOK_DOT,
    TOK_EXPREF,
    TOK_FILTER,
    TOK_FLATTEN,
    TOK_GLOBAL,
    TOK_IDENTIFIER,
    TOK_INT,
    TOK_JSON,
    TOK_LBRACE,
    TOK_LBRACKET,
    TOK_LPAREN,
    TOK_NOT,
    TOK_NUMBER,
    TOK_OR,
    TOK_PIPE,
    TOK_QUOTEDIDENTIFIER,
    TOK_RBRACE,
    TOK_RBRACKET,
    TOK_RPAREN,
    TOK_STAR,
    TOK_STRING,
    TOK_SUBTRACT,
    TOK_UNARY_MINUS,
    TOK_UNION,
)

BASIC_TOKENS = {
    ".": TOK_DOT,
    ",": TOK_COMMA,
    ":": TOK_COLON,
    "{": TOK_LBRACE,
    "}": TOK_RBRACE,
    "]": TOK_RBRACKET,
    "(": TOK_LPAREN,
    ")": TOK_RPAREN,
    "@": TOK_CURRENT,
}

SKIP_CHARS = {" ", "\t", "\n"}
OPERATOR_START = {"<", ">", "=", "!"}


def _is_alphanum(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _is_identifier(stream: str, pos: int) -> bool:
    ch = stream[pos]
    return ch == "$" or ch.isalpha() or ch == "_"


class Lexer:
    def __init__(self, allowed_global_names: list[str] | None = None, debug: list[str] | None = None) -> None:
        self.allowed_global_names = allowed_global_names or []
        self.debug = debug if debug is not None else []
        self.current = 0

    def tokenize(self, stream: str) -> list[dict[str, Any]]:
        tokens: list[dict[str, Any]] = []
        self.current = 0
        while self.current < len(stream):
            prev = tokens[-1]["type"] if tokens else None
            if self._is_global(prev, stream, self.current):
                tokens.append(self._consume_global(stream))
            elif _is_identifier(stream, self.current):
                start = self.current
                identifier = self._consume_unquoted_identifier(stream)
                tokens.append({"type": TOK_IDENTIFIER, "value": identifier, "start": start})
            elif self._is_number(stream):
                tokens.append(self._consume_number(stream))
            elif stream[self.current] in BASIC_TOKENS:
                tokens.append(
                    {"type": BASIC_TOKENS[stream[self.current]], "value": stream[self.current], "start": self.current}
                )
                self.current += 1
            elif stream[self.current] == "-" and prev not in {
                TOK_GLOBAL,
                TOK_CURRENT,
                TOK_NUMBER,
                TOK_INT,
                TOK_RPAREN,
                TOK_IDENTIFIER,
                TOK_QUOTEDIDENTIFIER,
                TOK_RBRACKET,
                TOK_JSON,
                TOK_STRING,
            }:
                tokens.append({"type": TOK_UNARY_MINUS, "value": "-", "start": self.current})
                self.current += 1
            elif stream[self.current] == "[":
                tokens.append(self._consume_lbracket(stream))
            elif stream[self.current] == "'":
                start = self.current
                value = self._consume_quoted_identifier(stream)
                tokens.append({"type": TOK_QUOTEDIDENTIFIER, "value": value, "start": start})
            elif stream[self.current] == '"':
                start = self.current
                value = self._consume_raw_string_literal(stream)
                tokens.append({"type": TOK_STRING, "value": value, "start": start})
            elif stream[self.current] == "`":
                start = self.current
                value = self._consume_json(stream)
                tokens.append({"type": TOK_JSON, "value": value, "start": start})
            elif stream[self.current] in OPERATOR_START:
                tokens.append(self._consume_operator(stream))
            elif stream[self.current] in SKIP_CHARS:
                self.current += 1
            elif stream[self.current] == "&":
                start = self.current
                self.current += 1
                if self.current < len(stream) and stream[self.current] == "&":
                    self.current += 1
                    tokens.append({"type": TOK_AND, "value": "&&", "start": start})
                elif prev in {TOK_COMMA, TOK_LPAREN}:
                    tokens.append({"type": TOK_EXPREF, "value": "&", "start": start})
                else:
                    tokens.append({"type": TOK_CONCATENATE, "value": "&", "start": start})
            elif stream[self.current] == "~":
                tokens.append({"type": TOK_UNION, "value": "~", "start": self.current})
                self.current += 1
            elif stream[self.current] == "+":
                tokens.append({"type": TOK_ADD, "value": "+", "start": self.current})
                self.current += 1
            elif stream[self.current] == "-":
                tokens.append({"type": TOK_SUBTRACT, "value": "-", "start": self.current})
                self.current += 1
            elif stream[self.current] == "*":
                tokens.append({"type": TOK_STAR, "value": "*", "start": self.current})
                self.current += 1
            elif stream[self.current] == "/":
                tokens.append({"type": TOK_DIVIDE, "value": "/", "start": self.current})
                self.current += 1
            elif stream[self.current] == "|":
                start = self.current
                self.current += 1
                if self.current < len(stream) and stream[self.current] == "|":
                    self.current += 1
                    tokens.append({"type": TOK_OR, "value": "||", "start": start})
                else:
                    tokens.append({"type": TOK_PIPE, "value": "|", "start": start})
            else:
                raise syntax_error(f"Unknown character:{stream[self.current]}")
        return tokens

    def _consume_unquoted_identifier(self, stream: str) -> str:
        start = self.current
        self.current += 1
        while self.current < len(stream) and (stream[self.current] == "$" or _is_alphanum(stream[self.current])):
            self.current += 1
        return stream[start : self.current]

    def _consume_quoted_identifier(self, stream: str) -> str:
        start = self.current
        self.current += 1
        max_length = len(stream)
        found_non_alpha = not _is_identifier(stream, start + 1)
        while self.current < max_length and stream[self.current] != "'":
            current = self.current
            if not _is_alphanum(stream[current]):
                found_non_alpha = True
            if stream[current] == "\\" and current + 1 < max_length and stream[current + 1] in {"\\", "'"}:
                current += 2
            else:
                current += 1
            self.current = current
        if self.current >= max_length:
            raise syntax_error(f"Unterminated quoted identifier at {start}")
        self.current += 1
        raw = stream[start : self.current]
        if not found_non_alpha:
            self.debug.append(f"Suspicious quotes: {raw}")
            self.debug.append(f'Did you intend a literal? "{raw.replace(chr(39), "")}"?')
        body = raw[1:-1].replace("\\'", "'")
        try:
            return json.loads(f'"{body}"')
        except json.JSONDecodeError as exc:
            raise syntax_error(f"Invalid quoted identifier: {raw}") from exc

    def _consume_raw_string_literal(self, stream: str) -> str:
        start = self.current
        self.current += 1
        max_length = len(stream)
        while self.current < max_length and stream[self.current] != '"':
            current = self.current
            if stream[current] == "\\" and current + 1 < max_length and stream[current + 1] in {"\\", '"'}:
                current += 2
            else:
                current += 1
            self.current = current
        if self.current >= max_length:
            raise syntax_error(f'Unterminated string literal at {start}, "{stream[start + 1:]}' )
        self.current += 1
        literal = stream[start + 1 : self.current - 1]
        if self.current > max_length + 1:
            raise syntax_error(f'Unterminated string literal at {start}, "{literal}')
        try:
            return json.loads(f'"{literal}"')
        except json.JSONDecodeError as exc:
            raise syntax_error(f"Invalid string literal: {literal}") from exc

    def _is_number(self, stream: str) -> bool:
        ch = stream[self.current]
        if ch.isdigit():
            return True
        return ch == "." and self.current + 1 < len(stream) and stream[self.current + 1].isdigit()

    def _consume_number(self, stream: str) -> dict[str, Any]:
        start = self.current
        match = re.match(r"^[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", stream[start:])
        if not match:
            raise syntax_error(f"Invalid number: {stream[start:]}")
        token = match.group(0)
        self.current += len(token)
        if "." in token or "e" in token.lower():
            return {"type": TOK_NUMBER, "value": float(token), "start": start}
        return {"type": TOK_INT, "value": int(token), "start": start}

    def _consume_lbracket(self, stream: str) -> dict[str, Any]:
        start = self.current
        self.current += 1
        if self.current < len(stream) and stream[self.current] == "?":
            self.current += 1
            return {"type": TOK_FILTER, "value": "[?", "start": start}
        if self.current < len(stream) and stream[self.current] == "]":
            self.current += 1
            return {"type": TOK_FLATTEN, "value": "[]", "start": start}
        return {"type": TOK_LBRACKET, "value": "[", "start": start}

    def _is_global(self, prev: str | None, stream: str, pos: int) -> bool:
        if prev == TOK_DOT:
            return False
        if stream[pos] != "$":
            return False
        i = pos + 1
        while i < len(stream) and (stream[i] == "$" or _is_alphanum(stream[i])):
            i += 1
        return stream[pos:i] in self.allowed_global_names

    def _consume_global(self, stream: str) -> dict[str, Any]:
        start = self.current
        self.current += 1
        while self.current < len(stream) and (stream[self.current] == "$" or _is_alphanum(stream[self.current])):
            self.current += 1
        return {"type": TOK_GLOBAL, "name": stream[start : self.current], "start": start}

    def _consume_operator(self, stream: str) -> dict[str, Any]:
        start = self.current
        ch = stream[start]
        self.current += 1
        if ch == "!":
            if self.current < len(stream) and stream[self.current] == "=":
                self.current += 1
                return {"type": TOK_COMPARATOR, "value": "!=", "start": start}
            return {"type": TOK_NOT, "value": "!", "start": start}
        if ch == "<":
            if self.current < len(stream) and stream[self.current] == "=":
                self.current += 1
                return {"type": TOK_COMPARATOR, "value": "<=", "start": start}
            if self.current < len(stream) and stream[self.current] == ">":
                self.current += 1
                return {"type": TOK_COMPARATOR, "value": "!=", "start": start}
            return {"type": TOK_COMPARATOR, "value": "<", "start": start}
        if ch == ">":
            if self.current < len(stream) and stream[self.current] == "=":
                self.current += 1
                return {"type": TOK_COMPARATOR, "value": ">=", "start": start}
            return {"type": TOK_COMPARATOR, "value": ">", "start": start}
        if self.current < len(stream) and stream[self.current] == "=":
            self.current += 1
        return {"type": TOK_COMPARATOR, "value": "==", "start": start}

    def _consume_json(self, stream: str) -> Any:
        self.current += 1
        start = self.current
        max_length = len(stream)
        in_string = False
        escaped = False
        while self.current < max_length:
            char = stream[self.current]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "`":
                    raise syntax_error(f"Unterminated JSON literal at {start}: `{stream[start:self.current]}")
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "`":
                    break
            self.current += 1
        if self.current >= max_length:
            tail = stream[start:].replace("\\`", "`")
            raise syntax_error(f"Unterminated JSON literal at {start}: `{tail}")
        literal = stream[start : self.current].lstrip().replace("\\`", "`")
        self.current += 1
        if self.current > max_length + 1:
            raise syntax_error(f"Unterminated JSON literal at {start}: `{literal}")
        try:
            return json.loads(literal)
        except json.JSONDecodeError as exc:
            raise syntax_error(str(exc)) from exc
