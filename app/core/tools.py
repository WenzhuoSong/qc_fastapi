"""
Custom Tool Definitions
Provide additional functionality for CrewAI agents
"""

from crewai.tools import tool
import requests
from typing import Optional


@tool("web_search")
def web_search(query: str, num_results: int = 5) -> str:
    """
    Perform web search to get information
    
    Args:
        query: Search query
        num_results: Number of results to return (default 5)
        
    Returns:
        Summary text of search results
    """
    # Actual search logic can be implemented here
    # For example using SerpAPI, Google Custom Search, etc.
    
    # Example implementation (simulated)
    return f"Search results for '{query}':\n" \
           f"1. Sample result 1\n" \
           f"2. Sample result 2\n" \
           f"3. More results..."


@tool("fetch_webpage")
def fetch_webpage(url: str) -> str:
    """
    Fetch webpage content
    
    Args:
        url: Webpage URL
        
    Returns:
        Text content of the webpage
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # HTML parsing logic can be added here
        return response.text[:2000]  # Limit return length
    except Exception as e:
        return f"Failed to fetch webpage: {str(e)}"


@tool("calculate")
def calculate(expression: str) -> str:
    """
    Perform mathematical calculation
    
    Args:
        expression: Mathematical expression (e.g., "2 + 2")
        
    Returns:
        Calculation result
    """
    try:
        # Safe calculation - only allow basic math operations
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "Error: Expression contains disallowed characters"
        
        result = eval(expression)
        return f"Calculation result: {result}"
    except Exception as e:
        return f"Calculation error: {str(e)}"


@tool("save_to_file")
def save_to_file(content: str, filename: str) -> str:
    """
    Save content to file
    
    Args:
        content: Content to save
        filename: Filename
        
    Returns:
        Save result message
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Content successfully saved to {filename}"
    except Exception as e:
        return f"Save failed: {str(e)}"
