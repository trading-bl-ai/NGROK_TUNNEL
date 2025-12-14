"""
Message protocol for serializing/deserializing HTTP requests and responses
"""
import base64
from typing import Dict, Optional
from fastapi import Request
from tunnel.tunnel_models import HTTPRequest, HTTPResponse, TunnelMessage
import json


def is_binary_content(content_type: str) -> bool:
    """Check if content type is binary"""
    binary_types = [
        "image/", "video/", "audio/", "application/octet-stream",
        "application/pdf", "application/zip", "application/x-tar"
    ]
    return any(bt in content_type.lower() for bt in binary_types)


async def serialize_request(request: Request, path: str, request_id: str) -> HTTPRequest:
    """
    Serialize FastAPI Request to HTTPRequest model

    Args:
        request: FastAPI Request object
        path: Request path
        request_id: Unique request identifier

    Returns:
        HTTPRequest model
    """
    # Get headers as dict
    headers = dict(request.headers)

    # Get query parameters
    query_params = dict(request.query_params)

    # Get body
    body_bytes = await request.body()
    body_str = None

    if body_bytes:
        content_type = headers.get("content-type", "")
        if is_binary_content(content_type):
            # Base64 encode binary content
            body_str = base64.b64encode(body_bytes).decode("utf-8")
            headers["x-tunnel-body-encoding"] = "base64"
        else:
            # Try to decode as UTF-8
            try:
                body_str = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback to base64 if decode fails
                body_str = base64.b64encode(body_bytes).decode("utf-8")
                headers["x-tunnel-body-encoding"] = "base64"

    return HTTPRequest(
        request_id=request_id,
        method=request.method,
        path=path,
        headers=headers,
        body=body_str,
        query_params=query_params
    )


def deserialize_request(http_request: HTTPRequest) -> Dict:
    """
    Convert HTTPRequest model to dict for client processing

    Args:
        http_request: HTTPRequest model

    Returns:
        Dictionary with request details
    """
    body = None
    if http_request.body:
        if http_request.headers.get("x-tunnel-body-encoding") == "base64":
            body = base64.b64decode(http_request.body)
        else:
            body = http_request.body.encode("utf-8") if isinstance(http_request.body, str) else http_request.body

    return {
        "request_id": http_request.request_id,
        "method": http_request.method,
        "path": http_request.path,
        "headers": http_request.headers,
        "body": body,
        "query_params": http_request.query_params
    }


def serialize_response(response_data: Dict) -> HTTPResponse:
    """
    Serialize response data to HTTPResponse model

    Args:
        response_data: Dict with status_code, headers, body, request_id

    Returns:
        HTTPResponse model
    """
    body_str = None
    headers = response_data.get("headers", {})

    if "body" in response_data and response_data["body"]:
        body = response_data["body"]

        if isinstance(body, bytes):
            content_type = headers.get("content-type", "")
            if is_binary_content(content_type):
                body_str = base64.b64encode(body).decode("utf-8")
                headers["x-tunnel-body-encoding"] = "base64"
            else:
                try:
                    body_str = body.decode("utf-8")
                except UnicodeDecodeError:
                    body_str = base64.b64encode(body).decode("utf-8")
                    headers["x-tunnel-body-encoding"] = "base64"
        else:
            body_str = str(body)

    return HTTPResponse(
        request_id=response_data["request_id"],
        status_code=response_data.get("status_code", 200),
        headers=headers,
        body=body_str
    )


def deserialize_response(http_response: HTTPResponse) -> Dict:
    """
    Convert HTTPResponse model to dict for returning to client

    Args:
        http_response: HTTPResponse model

    Returns:
        Dictionary with response details
    """
    body = None
    if http_response.body:
        if http_response.headers.get("x-tunnel-body-encoding") == "base64":
            body = base64.b64decode(http_response.body)
        else:
            body = http_response.body.encode("utf-8") if isinstance(http_response.body, str) else http_response.body

    return {
        "status_code": http_response.status_code,
        "headers": http_response.headers,
        "body": body
    }


def create_tunnel_message(msg_type: str, data: Optional[Dict] = None) -> str:
    """
    Create a WebSocket message

    Args:
        msg_type: Message type (request, response, ping, pong, error)
        data: Message payload

    Returns:
        JSON string
    """
    message = TunnelMessage(type=msg_type, data=data)
    return message.model_dump_json()


def parse_tunnel_message(message_str: str) -> TunnelMessage:
    """
    Parse a WebSocket message

    Args:
        message_str: JSON string

    Returns:
        TunnelMessage model
    """
    return TunnelMessage.model_validate_json(message_str)
