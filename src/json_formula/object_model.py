"""Helpers for the optional field-object execution model used by the official tests."""

from __future__ import annotations

from typing import Any


class Field:
    def __init__(self, name: str, value: Any, readonly: bool = False, required: bool = True) -> None:
        self._name = name
        self._value = value
        self._readonly = readonly
        self._required = required

    @property
    def value(self) -> Any:
        return self._value

    @property
    def value_of(self) -> Any:
        return self._value

    @property
    def to_json(self) -> Any:
        return self._value

    @property
    def dollar_name(self) -> str:
        return self._name

    @property
    def dollar_value(self) -> Any:
        return self._value

    @property
    def dollar_readonly(self) -> bool:
        return self._readonly

    @property
    def dollar_required(self) -> bool:
        return self._required


class FieldsetObject(dict):
    def __init__(self, name: str, fields: list[Any]) -> None:
        super().__init__()
        self._name = name
        self._fields = fields

    @property
    def dollar_name(self) -> str:
        return self._name

    @property
    def dollar_fields(self) -> list[Any]:
        return self._fields

    @property
    def dollar_value(self) -> dict[str, Any]:
        return {key: value for key, value in self.items()}


class FieldsetArray(list):
    def __init__(self, name: str, fields: list[Any]) -> None:
        super().__init__()
        self._name = name
        self._fields = fields

    @property
    def dollar_name(self) -> str:
        return self._name

    @property
    def dollar_fields(self) -> list[Any]:
        return self._fields

    @property
    def dollar_value(self) -> list[Any]:
        return list(self)


def _create_fields(parent: Any, child_ref: Any, child: Any) -> list[Any]:
    result: list[Any] = []
    if isinstance(child, list):
        fieldset = FieldsetArray(str(child_ref), result)
        if isinstance(parent, list):
            parent.append(fieldset)
        else:
            parent[child_ref] = fieldset
        for index, item in enumerate(child):
            result.extend(_create_fields(fieldset, index, item))
        return result
    if isinstance(child, dict):
        fieldset = FieldsetObject(str(child_ref), result)
        if isinstance(parent, list):
            parent.append(fieldset)
        else:
            parent[child_ref] = fieldset
        for key, value in child.items():
            result.extend(_create_fields(fieldset, key, value))
        return result

    field = Field(str(child_ref), child)
    if isinstance(parent, list):
        parent.append(field)
    else:
        parent[child_ref] = field
    result.append(field)
    return result


def create_form(data_root: Any) -> Any:
    if data_root is None or not isinstance(data_root, (dict, list)):
        return data_root
    all_fields: list[Any] = []
    root = FieldsetObject("", all_fields) if isinstance(data_root, dict) else FieldsetArray("", all_fields)
    if isinstance(data_root, dict):
        for key, value in data_root.items():
            all_fields.extend(_create_fields(root, key, value))
    else:
        for index, value in enumerate(data_root):
            all_fields.extend(_create_fields(root, index, value))
    return root
