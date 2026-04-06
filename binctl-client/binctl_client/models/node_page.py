from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.node import Node


T = TypeVar("T", bound="NodePage")


@_attrs_define
class NodePage:
    """
    Attributes:
        total (int):
        limit (int):
        offset (int):
        items (list[Node]):
    """

    total: int
    limit: int
    offset: int
    items: list[Node]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "items": [n.to_dict() for n in self.items],
        }

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.node import Node

        d = dict(src_dict)
        total = d.pop("total")
        limit = d.pop("limit")
        offset = d.pop("offset")
        items = [Node.from_dict(item) for item in d.pop("items")]

        page = cls(total=total, limit=limit, offset=offset, items=items)
        page.additional_properties = d
        return page

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
