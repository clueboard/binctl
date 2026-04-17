from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="DeleteNodeEndpointResponse200Deleted")


@_attrs_define
class DeleteNodeEndpointResponse200Deleted:
    """
    Attributes:
        total (int):
        edges (int):
        tags (int):
        nodes (int):
    """

    total: int
    edges: int
    tags: int
    nodes: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        total = self.total

        edges = self.edges

        tags = self.tags

        nodes = self.nodes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "total": total,
                "edges": edges,
                "tags": tags,
                "nodes": nodes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        total = d.pop("total")

        edges = d.pop("edges")

        tags = d.pop("tags")

        nodes = d.pop("nodes")

        delete_node_endpoint_response_200_deleted = cls(
            total=total,
            edges=edges,
            tags=tags,
            nodes=nodes,
        )

        delete_node_endpoint_response_200_deleted.additional_properties = d
        return delete_node_endpoint_response_200_deleted

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
