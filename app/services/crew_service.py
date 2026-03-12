"""
CrewAI Service Layer
Orchestrates agents and tasks defined in separate modules.
"""

import time
import asyncio
from typing import List, Optional, Dict, Any

from app.config import settings
from app.services.agents import create_default_agents, CREWAI_AVAILABLE
from app.services.tasks_def import create_default_tasks
from app.core.cache import get_cached_result, set_cached_result, make_cache_key

try:
    from crewai import Crew, Process
except ImportError:
    class Crew:                                           # type: ignore[no-redef]
        def __init__(self, agents=None, tasks=None, verbose=True, process=None):
            self.agents = agents
            self.tasks = tasks
            self.verbose = verbose
            self.process = process

        def kickoff(self):
            return "Mock crew execution result"

    class Process:                                        # type: ignore[no-redef]
        sequential = "sequential"


class CrewService:
    """CrewAI Service Class"""

    def __init__(self):
        self.default_agents = create_default_agents()
        self.default_tasks = create_default_tasks(self.default_agents)

    async def run_crew(
        self,
        topic: str,
        agents_config: Optional[List[Dict[str, Any]]] = None,
        tasks_config: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run CrewAI agent team, with TTL caching to avoid duplicate LLM calls."""
        cache_key = make_cache_key(topic)
        cached = get_cached_result(cache_key)
        if cached is not None:
            return {**cached, "from_cache": True}

        start_time = time.time()

        if not CREWAI_AVAILABLE:
            await asyncio.sleep(0.5)
            result = {
                "output": f"Mock result for topic: {topic}\n\nCrewAI is not installed. This is a mock response for testing purposes.",
                "execution_time": round(time.time() - start_time, 2),
                "tasks_completed": 3,
                "note": "Running in mock mode - CrewAI not installed",
            }
            set_cached_result(cache_key, result)
            return result

        agents = self.default_agents
        tasks = self.default_tasks

        for task in tasks:
            if hasattr(task, "description"):
                task.description = task.description.format(topic=topic)

        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential,
        )

        loop = asyncio.get_event_loop()
        raw_result = await loop.run_in_executor(None, crew.kickoff)

        execution_time = time.time() - start_time
        result = {
            "output": str(raw_result),
            "execution_time": round(execution_time, 2),
            "tasks_completed": len(tasks),
        }
        set_cached_result(cache_key, result)
        return result

    def get_default_crew_info(self) -> Dict[str, Any]:
        """Get default Crew configuration information."""
        return {
            "name": "Content Creation Team",
            "description": "A content creation team consisting of a researcher, writer, and editor",
            "crewai_available": CREWAI_AVAILABLE,
            "agents": [
                {
                    "role": agent.role,
                    "goal": agent.goal,
                    "backstory": agent.backstory[:100] + "..." if len(agent.backstory) > 100 else agent.backstory,
                }
                for agent in self.default_agents
            ],
            "tasks": [
                {
                    "description": task.description[:100] + "..." if len(task.description) > 100 else task.description,
                    "expected_output": task.expected_output,
                }
                for task in self.default_tasks
            ],
        }
