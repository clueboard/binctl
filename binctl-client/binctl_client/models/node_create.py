from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="NodeCreate")


@_attrs_define
class NodeCreate:
    """
    Attributes:
        label (str):
        description (None | str | Unset):
        is_container (bool | Unset):  Default: False.
        parent_id (int | None | Unset):
        tag_ids (list[int] | Unset):
    """

    label: str
    description: None | str | Unset = UNSET
    is_container: bool | Unset = False
    parent_id: int | None | Unset = UNSET
    tag_ids: list[int] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        label = self.label

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        is_container = self.is_container

        parent_id: int | None | Unset
        if isinstance(self.parent_id, Unset):
            parent_id = UNSET
        else:
            parent_id = self.parent_id

        tag_ids: list[int] | Unset = UNSET
        if not isinstance(self.tag_ids, Unset):
            tag_ids = self.tag_ids

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "label": label,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if is_container is not UNSET:
            field_dict["is_container"] = is_container
        if parent_id is not UNSET:
            field_dict["parent_id"] = parent_id
        if tag_ids is not UNSET:
            field_dict["tag_ids"] = tag_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        label = d.pop("label")

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        is_container = d.pop("is_container", UNSET)

        def _parse_parent_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        parent_id = _parse_parent_id(d.pop("parent_id", UNSET))

        tag_ids = cast(list[int], d.pop("tag_ids", UNSET))

        node_create = cls(
            label=label,
            description=description,
            is_container=is_container,
            parent_id=parent_id,
            tag_ids=tag_ids,
        )

        node_create.additional_properties = d
        return node_create

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
