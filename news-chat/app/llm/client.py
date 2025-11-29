"""
LLM Client - Handles communication with Ollama or API providers
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx
import ollama

from ..config import settings
from .tools import MCP_TOOLS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for LLM interactions with tool-calling support."""
    
    def __init__(self):
        self.ollama_client = ollama.AsyncClient(host=settings.ollama_url)
        self.model = settings.ollama_model
        self.tools = MCP_TOOLS
        
    async def check_connection(self) -> bool:
        """Check if Ollama is available."""
        try:
            await self.ollama_client.list()
            return True
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False
    
    async def chat(
        self,
        messages: list[dict],
        tool_executor: Optional[callable] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response, handling tool calls if needed.
        
        Args:
            messages: Chat history
            tool_executor: Async function to execute tool calls
            
        Yields:
            Response text chunks
        """
        # Add system prompt if not present
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        
        try:
            # First call - may include tool calls
            response = await self.ollama_client.chat(
                model=self.model,
                messages=messages,
                tools=self.tools,
                stream=False  # Need full response to check for tools
            )
            
            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            # If there are tool calls, execute them
            if tool_calls and tool_executor:
                logger.info(f"LLM requested {len(tool_calls)} tool call(s)")
                
                # Add assistant message with tool calls
                messages.append(message)
                
                # Execute each tool call
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"]["arguments"]
                    
                    yield f"\n🔧 *Calling {func_name}...*\n"
                    
                    try:
                        # Execute the tool
                        result = await tool_executor(func_name, func_args)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(result, ensure_ascii=False)
                        })
                        
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        messages.append({
                            "role": "tool",
                            "content": json.dumps({"error": str(e)})
                        })
                
                # Get final response with tool results - stream this one
                async for chunk in await self.ollama_client.chat(
                    model=self.model,
                    messages=messages,
                    stream=True
                ):
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
            else:
                # No tool calls, just yield the response
                content = message.get("content", "")
                if content:
                    yield content
                    
        except ollama.ResponseError as e:
            logger.error(f"Ollama error: {e}")
            yield f"Error communicating with LLM: {e}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            yield f"An error occurred: {e}"
    
    async def simple_chat(self, messages: list[dict]) -> str:
        """Non-streaming chat without tools (for simple queries)."""
        try:
            response = await self.ollama_client.chat(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Simple chat error: {e}")
            return f"Error: {e}"


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
