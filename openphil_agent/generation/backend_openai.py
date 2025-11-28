"""Backend for OpenAI API."""

import json
import logging
import time
import os
from .utils import FunctionSpec, OutputType, opt_messages_to_list, backoff_create
from funcy import notnone, once, select_values
import openai

logger = logging.getLogger("backend")

_client: openai.OpenAI = None  # type: ignore

OPENAI_TIMEOUT_EXCEPTIONS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


@once
def _setup_openai_client():
    global _client
    _client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", 
                            api_key=os.environ["OPENROUTER_API_KEY"],
                            max_retries=0)


def query(
    system_message: str | None,
    user_message: str | None,
    tool_dict: dict[str, FunctionSpec] | None = None,
    tool_choice: str = "auto",
    **model_kwargs,
) -> tuple[OutputType, float, int, int, dict]:
    """
    Query the OpenAI API, optionally with function calling.
    If the model doesn't support function calling, gracefully degrade to text generation.
    """
    _setup_openai_client()
    filtered_kwargs: dict = select_values(notnone, model_kwargs)

    # Convert system/user messages to the format required by the client
    messages = opt_messages_to_list(system_message, user_message)

    # If function calling is requested, attach the function spec
    if tool_dict is not None:
        filtered_kwargs["tools"] = [tool.as_openai_tool_dict for tool in tool_dict.values()]
        filtered_kwargs["tool_choice"] = tool_dict[tool_choice].openai_tool_choice_dict if tool_choice in tool_dict else tool_choice

    completion = None
    t0 = time.time()

    # Attempt the API call
    try:
        completion = backoff_create(
            _client.chat.completions.create,
            OPENAI_TIMEOUT_EXCEPTIONS,
            messages=messages,
            **filtered_kwargs,
        )
    except openai.BadRequestError as e:
        # Check whether the error indicates that function calling is not supported
        if "function calling" in str(e).lower() or "tools" in str(e).lower():
            logger.warning(
                "Function calling was attempted but is not supported by this model. "
                "Falling back to plain text generation."
            )
            # Remove function-calling parameters and retry
            filtered_kwargs.pop("tools", None)
            filtered_kwargs.pop("tool_choice", None)

            # Retry without function calling
            completion = backoff_create(
                _client.chat.completions.create,
                OPENAI_TIMEOUT_EXCEPTIONS,
                messages=messages,
                **filtered_kwargs,
            )
        else:
            # If it's some other error, re-raise
            raise

    req_time = time.time() - t0
    choice = completion.choices[0]

    # Extract the output text
    output_text = choice.message.content
    filtered_tool_calls = []

    if tool_dict is not None:
        # Attempt to extract tool calls
        tool_calls = getattr(choice.message, "tool_calls", None)
        if not tool_calls:
            logger.warning(
                "Note: No function call was used despite function spec. Fallback to text.\n"
                f"Message content: {choice.message.content}"
            )
        else:
            for tool_call in tool_calls:
                # Optional: verify that the function name matches
                if tool_call.function.name not in tool_dict:
                    logger.warning(
                        f"Tool {tool_call} was used but does not exist in tool_dict: {tool_dict.keys()}"
                        f"Returning text message only."
                    )
                else:
                    try:
                        filtered_tool_calls.append((tool_call.function.name, json.loads(tool_call.function.arguments)))
                    except json.JSONDecodeError as ex:
                        logger.error(
                            f"Error decoding function {tool_call.function.name} with arguments:\n"
                            f"{tool_call.function.arguments}"
                        )
                        raise ex

    in_tokens = completion.usage.prompt_tokens
    out_tokens = completion.usage.completion_tokens

    info = {
        "system_fingerprint": completion.system_fingerprint,
        "model": completion.model,
        "created": completion.created,
    }

    return output_text, filtered_tool_calls, req_time, in_tokens, out_tokens, info