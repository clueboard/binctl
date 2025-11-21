from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.tag import Tag
from ...types import Response


def _get_kwargs(
    tag_id: int,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/v1/tag/{tag_id}",
    }

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
) -> Response[Any | Tag]:
    """Get tag by ID

    Args:
        tag_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | Tag]
    """

    kwargs = _get_kwargs(
        tag_id=tag_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Any | Tag | None:
    """Get tag by ID

    Args:
        tag_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | Tag
    """

    return sync_detailed(
        tag_id=tag_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Any | Tag]:
    """Get tag by ID

    Args:
        tag_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | Tag]
    """

    kwargs = _get_kwargs(
        tag_id=tag_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    tag_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Any | Tag | None:
    """Get tag by ID

    Args:
        tag_id (int):

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
        )
    ).parsed
