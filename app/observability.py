"""
Observability and LangSmith integration.
"""

import inspect
import os
from functools import wraps
from typing import Any, Callable

from config.settings import settings


def configure_langsmith() -> None:
    """
    Configure LangSmith environment variables.
    """

    if not settings.langchain_tracing_v2:
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = (
        settings.langchain_api_key
    )
    os.environ["LANGCHAIN_PROJECT"] = (
        settings.langchain_project
    )

    # Use the configured endpoint when available.
    endpoint = getattr(
        settings,
        "langchain_endpoint",
        None,
    )

    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint


def trace(name: str) -> Callable:
    """
    Trace a function in LangSmith while retaining
    the existing console trace messages.
    """

    from langsmith import traceable

    def decorator(function: Callable) -> Callable:

        # Create the actual LangSmith wrapper.
        traced_function = traceable(
            name=name
        )(function)

        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(
                *args: Any,
                **kwargs: Any,
            ) -> Any:

                if settings.debug:
                    print(
                        f"[TRACE] START: {name}"
                    )

                try:
                    result = await traced_function(
                        *args,
                        **kwargs,
                    )

                    if settings.debug:
                        print(
                            f"[TRACE] END: {name}"
                        )

                    return result

                except Exception as exc:

                    if settings.debug:
                        print(
                            f"[TRACE] ERROR: "
                            f"{name}: {exc}"
                        )

                    raise

            return async_wrapper

        @wraps(function)
        def sync_wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:

            if settings.debug:
                print(
                    f"[TRACE] START: {name}"
                )

            try:
                result = traced_function(
                    *args,
                    **kwargs,
                )

                if settings.debug:
                    print(
                        f"[TRACE] END: {name}"
                    )

                return result

            except Exception as exc:

                if settings.debug:
                    print(
                        f"[TRACE] ERROR: "
                        f"{name}: {exc}"
                    )

                raise

        return sync_wrapper

    return decorator