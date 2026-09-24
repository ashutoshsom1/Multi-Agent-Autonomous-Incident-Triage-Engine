"""Model Context Protocol (MCP) client and tool abstractions."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel


class MCPToolDefinition(BaseModel):
    """Specification of an MCP tool registered in the engine."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable[..., Any]] = None


class BaseMCPClient(ABC):
    """Abstract base class for Model Context Protocol client connections."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call over the Model Context Protocol."""
        pass

    @abstractmethod
    def list_tools(self) -> List[MCPToolDefinition]:
        """List available tools exposed by the MCP server."""
        pass
