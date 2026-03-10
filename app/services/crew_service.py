"""
CrewAI Service Layer
Handles agent team creation and execution
"""

import time
import asyncio
from typing import List, Optional, Dict, Any

# Try to import crewai, fallback to mock if not available
try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # Mock classes for testing without crewai
    class Agent:
        def __init__(self, role, goal, backstory, verbose=True, allow_delegation=False):
            self.role = role
            self.goal = goal
            self.backstory = backstory
            self.verbose = verbose
            self.allow_delegation = allow_delegation
    
    class Task:
        def __init__(self, description, expected_output, agent, context=None):
            self.description = description
            self.expected_output = expected_output
            self.agent = agent
            self.context = context or []
    
    class Crew:
        def __init__(self, agents, tasks, verbose=True, process=None):
            self.agents = agents
            self.tasks = tasks
            self.verbose = verbose
            self.process = process
        
        def kickoff(self):
            return "Mock crew execution result"
    
    class Process:
        sequential = "sequential"

from app.config import settings


class CrewService:
    """CrewAI Service Class"""
    
    def __init__(self):
        self.default_agents = self._create_default_agents()
        self.default_tasks = self._create_default_tasks()
    
    def _create_default_agents(self) -> List[Agent]:
        """Create default agent team"""
        
        researcher = Agent(
            role="Researcher",
            goal="Conduct in-depth research on specified topics, collecting comprehensive and accurate information",
            backstory="""You are an experienced researcher skilled in information gathering and analysis.
            You excel at using various tools to find information and can critically evaluate the reliability of sources.
            You always provide detailed, accurate, and structured research findings.""",
            verbose=True,
            allow_delegation=False,
        )
        
        writer = Agent(
            role="Content Writer",
            goal="Transform research content into high-quality, readable articles",
            backstory="""You are a professional content creator skilled at transforming complex information into accessible content.
            You focus on article structure, logic, and readability, adjusting writing style for target audiences.
            Your articles are always engaging and informative.""",
            verbose=True,
            allow_delegation=False,
        )
        
        editor = Agent(
            role="Editor",
            goal="Review content quality to ensure accuracy and consistency",
            backstory="""You are a senior editor with extremely high standards for content quality.
            You excel at spotting errors, improving expression, and ensuring content meets professional standards.
            Your review makes every article publication-ready.""",
            verbose=True,
            allow_delegation=False,
        )
        
        return [researcher, writer, editor]
    
    def _create_default_tasks(self) -> List[Task]:
        """Create default task workflow"""
        
        research_task = Task(
            description="""Conduct in-depth research on the topic '{topic}'.
            
            Requirements:
            1. Collect core concepts and key information about this topic
            2. Identify relevant latest developments and trends
            3. Identify main viewpoints and controversies
            4. Organize into a structured research report
            
            Output format:
            - Topic overview
            - Key points (at least 5)
            - Relevant data and facts
            - Suggested information sources
            """,
            expected_output="A detailed research report containing core information and key findings about the topic",
            agent=self.default_agents[0],  # Researcher
        )
        
        writing_task = Task(
            description="""Based on the research report, write a high-quality article about '{topic}'.
            
            Requirements:
            1. Use information from the research report
            2. Clear article structure with introduction, body, and conclusion
            3. Language should be accessible and suitable for general readers
            4. Length between 800-1200 words
            5. Add appropriate headings and subheadings
            
            Note: Ensure content accuracy, do not add unverified information.
            """,
            expected_output="A well-structured, content-rich article",
            agent=self.default_agents[1],  # Writer
            context=[research_task],
        )
        
        editing_task = Task(
            description="""Review and improve the article about '{topic}'.
            
            Requirements:
            1. Check factual accuracy
            2. Improve language expression and flow
            3. Ensure logical structure is sound
            4. Correct grammar and spelling errors
            5. Provide final polished version
            
            Output:
            - Modified final article
            - Summary of changes made
            """,
            expected_output="Final version of article after editorial review, with change summary",
            agent=self.default_agents[2],  # Editor
            context=[writing_task],
        )
        
        return [research_task, writing_task, editing_task]
    
    async def run_crew(
        self,
        topic: str,
        agents_config: Optional[List[Dict[str, Any]]] = None,
        tasks_config: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Run CrewAI agent team
        
        Args:
            topic: Task topic
            agents_config: Custom agent configuration (optional)
            tasks_config: Custom task configuration (optional)
            
        Returns:
            Execution result dictionary
        """
        start_time = time.time()
        
        if not CREWAI_AVAILABLE:
            # Mock execution for testing
            await asyncio.sleep(0.5)
            return {
                "output": f"Mock result for topic: {topic}\n\nCrewAI is not installed. This is a mock response for testing purposes.",
                "execution_time": round(time.time() - start_time, 2),
                "tasks_completed": 3,
                "note": "Running in mock mode - CrewAI not installed",
            }
        
        # Use default or custom configuration
        agents = self.default_agents
        tasks = self.default_tasks
        
        # If custom configuration is provided, process it here
        # Currently using default configuration but replacing topic
        
        # Update topic in task descriptions
        for task in tasks:
            if hasattr(task, 'description'):
                task.description = task.description.format(topic=topic)
        
        # Create Crew
        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential,  # Sequential execution
        )
        
        # Run crew in async environment
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, crew.kickoff)
        
        execution_time = time.time() - start_time
        
        return {
            "output": str(result),
            "execution_time": round(execution_time, 2),
            "tasks_completed": len(tasks),
        }
    
    def get_default_crew_info(self) -> Dict[str, Any]:
        """Get default Crew configuration information"""
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
