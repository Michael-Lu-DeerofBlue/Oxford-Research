from . import backend_openai
from .utils import FunctionSpec, OutputType, PromptType, compile_prompt_to_md


def query(
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tool_dict: dict[str, FunctionSpec] | None = None,
    tool_choice: str = "auto",
    **model_kwargs,
) -> OutputType:
    """
    General LLM query for various backends with a single system and user message.
    Supports function calling for some backends.

    Args:
        system_message (PromptType | None): Uncompiled system message (will generate a message following the OpenAI/Anthropic format)
        user_message (PromptType | None): Uncompiled user message (will generate a message following the OpenAI/Anthropic format)
        model (str): string identifier for the model to use (e.g. "gpt-4-turbo")
        temperature (float | None, optional): Temperature to sample at. Defaults to the model-specific default.
        max_tokens (int | None, optional): Maximum number of tokens to generate. Defaults to the model-specific max tokens.
        tool_dict (dict[str, FunctionSpec] | None, optional): Optional dictionary of FunctionSpec objects defining all possible function calls. If given, the return value will be a dict.
        tool_choice (str, optional): Can be used to specify a tool that the model is forced to use. If given must be one of the keys in tool_dict or one of "auto", "any" "none". Defaults to "auto" to let the model choose which tool to use.
        **model_kwargs: Additional model-specific keyword arguments

    Returns:
        OutputType: A tuple with first element the output text as string and second element a list of tuples of which each represents one tool call.
        Each tuple in the list is of the form (function_name, args), where args is a dictionary that can be unpacked directly into the actual function call. 
    """

    if not tool_dict is None and tool_choice not in ["auto", "any", "none"] and tool_choice not in tool_dict:
        raise ValueError(f"tool_choice: {tool_choice} must be one of 'auto', 'any', 'none' or a key in tool_dict: {tool_dict.keys()}")

    model_kwargs = model_kwargs | {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Handle models with beta limitations
    # ref: https://platform.openai.com/docs/guides/reasoning/beta-limitations
    if model.startswith("o1"):
        if system_message:
            user_message = system_message
        system_message = None
        model_kwargs["temperature"] = 1

    query_func =  backend_openai.query
    output_text, tool_calls, req_time, in_tok_count, out_tok_count, info = query_func(
        system_message=compile_prompt_to_md(system_message) if system_message else None,
        user_message=compile_prompt_to_md(user_message) if user_message else None,
        tool_dict=tool_dict,
        tool_choice=tool_choice,
        **model_kwargs,
    )

    return output_text, tool_calls