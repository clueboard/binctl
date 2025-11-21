from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.tag import Tag
from ...models.tag_update import TagUpdate
from ...types import Response


def _get_kwargs(
    tag_id: int,
    *,
    body: TagUpdate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": f"/v1/tag/{tag_id}",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Any | Tag | None:
    if response.status_code == 200:
        response_200 = Tag.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = cast(Any, None)
        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[Any | Tag]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: TagUpdate,
) -> Response[Any | Tag]:
    """Update a tag

    Args:
        tag_id (int):
        body (TagUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | Tag]
    """

    kwargs = _get_kwargs(
        tag_id=tag_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: TagUpdate,
) -> Any | Tag | None:
    """Update a tag

    Args:
        tag_id (int):
        body (TagUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | Tag
    """

    return sync_detailed(
        tag_id=tag_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: TagUpdate,
) -> Response[Any | Tag]:
    """Update a tag

    Args:
        tag_id (int):
        body (TagUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | Tag]
    """

    kwargs = _get_kwargs(
        tag_id=tag_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: TagUpdate,
) -> Any | Tag | None:
    """Update a tag

    Args:
        tag_id (int):
        body (TagUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | Tag
    """

    return (
        await asyncio_detailed(
            tag_id=tag_id,
            client=client,
            body=body,
        )
    ).parsed
