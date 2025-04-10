import functools
import logging
from typing import TypeVar, Callable

from fastmcp import FastMCP
from mcp.types import TextContent

T = TypeVar('T')

def handle_search_exceptions(func: Callable[..., T]) -> Callable[..., list[TextContent]]:
    """
    Decorator to handle exceptions in search client operations.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function that handles exceptions
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger()   
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            return [TextContent(type="text", text=f"Unexpected error in {func.__name__}: {str(e)}")]
    
    return wrapper

def with_exception_handling(tool_instance: object, mcp: FastMCP) -> None:
    """
    Register tools from a tool instance with automatic exception handling applied to all tools.
    
    This function temporarily replaces mcp.tool with a wrapped version that automatically
    applies the handle_search_exceptions decorator to all registered tool methods.
    
    Args:
        tool_instance: The tool instance that has a register_tools method
        mcp: The FastMCP instance used for tool registration
    """
    # Save the original tool method
    original_tool = mcp.tool

    @functools.wraps(original_tool)
    def wrapped_tool(*args, **kwargs):
        # Get the original decorator
        decorator = original_tool(*args, **kwargs)

        # Return a new decorator that applies both the exception handler and original decorator
        def combined_decorator(func):
            # First apply the exception handling decorator
            wrapped_func = handle_search_exceptions(func)
            # Then apply the original mcp.tool decorator
            return decorator(wrapped_func)

        return combined_decorator

    try:
        # Temporarily replace mcp.tool with our wrapped version
        mcp.tool = wrapped_tool

        # Call the registration method on the tool instance
        tool_instance.register_tools(mcp)
    finally:
        # Restore the original mcp.tool to avoid affecting other code that might use mcp.tool
        # This ensures that our modification is isolated to just this tool registration
        # and prevents multiple nested decorators if register_all_tools is called multiple times
        mcp.tool = original_tool