"""Client for the scoring model.

In production this talks to Amazon Bedrock through boto3. In development and in
CI it talks to the stub in stub_model/, which copies Bedrock's latency and its
error behaviour. Either way the errors this module raises are the real botocore
exception types, so calling code does not need to care which backend is active.
"""

import json

import httpx
from botocore.exceptions import ClientError, ReadTimeoutError

from rubric.config import settings


class _ModelClient:
    """Thin stand-in for the boto3 bedrock-runtime client."""

    def __init__(self, endpoint: str, read_timeout: int) -> None:
        self._endpoint = endpoint
        self._http = httpx.Client(
            timeout=read_timeout,
            limits=httpx.Limits(max_connections=512, max_keepalive_connections=64),
        )

    def invoke_model(self, modelId: str, body: str) -> dict:  # noqa: N803 (boto3 naming)
        try:
            response = self._http.post(
                f"{self._endpoint}/model/{modelId}/invoke",
                content=body,
                headers={"content-type": "application/json"},
            )
        except (httpx.ReadTimeout, httpx.PoolTimeout, httpx.ConnectTimeout) as exc:
            raise ReadTimeoutError(endpoint_url=self._endpoint, error=exc) from exc

        if response.status_code == 429:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ThrottlingException",
                        "Message": "Too many requests, please wait before trying again.",
                    }
                },
                "InvokeModel",
            )
        if response.status_code >= 500:
            raise ClientError(
                {"Error": {"Code": "InternalServerException", "Message": response.text}},
                "InvokeModel",
            )

        response.raise_for_status()
        return {"body": response.text}


_client = _ModelClient(settings.model_endpoint, settings.model_read_timeout)


def invoke(prompt: str) -> dict:
    """Send a prompt to the model and return the parsed response."""
    payload = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
    )
    raw = _client.invoke_model(modelId=settings.model_id, body=payload)
    return json.loads(raw["body"])
