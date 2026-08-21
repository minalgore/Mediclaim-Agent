"""
Observability and LangSmith integration.
"""

import inspect
import os
from functools import wraps
from typing import Any, Callable

from config.settings import settings


def trace(name: str) -> Callable:
    """
    Lightweight tracing decorator.

    Supports both synchronous and asynchronous functions.
    """

    def decorator(function: Callable) -> Callable:

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
                    result = await function(
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
                result = function(
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


def configure_langsmith() -> None:
    """
    Configure LangSmith environment variables.
    """

    if not settings.langchain_tracing_v2:
        return

    os.environ[
        "LANGCHAIN_TRACING_V2"
    ] = "true"

    os.environ[
        "LANGCHAIN_API_KEY"
    ] = settings.langchain_api_key

    os.environ[
        "LANGCHAIN_PROJECT"
    ] = settings.langchain_project
