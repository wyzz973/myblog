import httpx
import pytest

from app.services.pet_adapters import openai_compat as adapter

pytestmark = pytest.mark.asyncio


def _ok_handler(content: str = "你好"):
    async def _h(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [{"message": {"content": content}}],
        }
        return httpx.Response(200, json=body)
    return _h


def _fail_handler(status: int):
    async def _h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "boom"})
    return _h


async def test_chat_parses_openai_response():
    transport = httpx.MockTransport(_ok_handler("compiling..."))
    text = await adapter.chat(
        api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
        transport=transport,
    )
    assert text == "compiling..."


async def test_chat_sends_bearer_auth_and_correct_body():
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        captured["json"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    await adapter.chat(
        api_key="abc", base_url="https://example/v1", model="m1",
        system="sys", user="usr", max_tokens=80, temperature=0.5,
        transport=httpx.MockTransport(handler),
    )
    assert captured["auth"] == "Bearer abc"
    assert captured["url"] == "https://example/v1/chat/completions"
    assert "model" in captured["json"] and "m1" in captured["json"]
    assert "max_tokens" in captured["json"] and "80" in captured["json"]


async def test_chat_raises_on_4xx():
    transport = httpx.MockTransport(_fail_handler(401))
    with pytest.raises(adapter.OpenAICompatError):
        await adapter.chat(
            api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
            transport=transport,
        )


async def test_chat_raises_on_5xx():
    transport = httpx.MockTransport(_fail_handler(500))
    with pytest.raises(adapter.OpenAICompatError):
        await adapter.chat(
            api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
            transport=transport,
        )


async def test_chat_raises_on_empty_content():
    async def h(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
    with pytest.raises(adapter.OpenAICompatError):
        await adapter.chat(
            api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
            transport=httpx.MockTransport(h),
        )


async def test_chat_merges_extra_body():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    await adapter.chat(
        api_key="k", base_url="https://x/v1", model="m",
        system="s", user="u",
        extra_body={"thinking": {"type": "disabled"}},
        transport=httpx.MockTransport(handler),
    )
    assert "thinking" in captured["json"]
    assert "disabled" in captured["json"]
