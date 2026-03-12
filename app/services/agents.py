"""
CrewAI Agent Definitions

Each function returns a configured Agent instance.
Add new agents here — crew_service.py will pick them up automatically.
"""

from typing import List

try:
    from crewai import Agent
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

    class Agent:                                          # type: ignore[no-redef]
        def __init__(self, role="", goal="", backstory="", verbose=True, allow_delegation=False):
            self.role = role
            self.goal = goal
            self.backstory = backstory
            self.verbose = verbose
            self.allow_delegation = allow_delegation


def create_researcher() -> Agent:
    return Agent(
        role="Researcher",
        goal="Conduct in-depth research on specified topics, collecting comprehensive and accurate information",
        backstory=(
            "You are an experienced researcher skilled in information gathering and analysis. "
            "You excel at using various tools to find information and can critically evaluate "
            "the reliability of sources. You always provide detailed, accurate, and structured "
            "research findings."
        ),
        verbose=True,
        allow_delegation=False,
    )


def create_writer() -> Agent:
    return Agent(
        role="Content Writer",
        goal="Transform research content into high-quality, readable articles",
        backstory=(
            "You are a professional content creator skilled at transforming complex information "
            "into accessible content. You focus on article structure, logic, and readability, "
            "adjusting writing style for target audiences. Your articles are always engaging "
            "and informative."
        ),
        verbose=True,
        allow_delegation=False,
    )


def create_editor() -> Agent:
    return Agent(
        role="Editor",
        goal="Review content quality to ensure accuracy and consistency",
        backstory=(
            "You are a senior editor with extremely high standards for content quality. "
            "You excel at spotting errors, improving expression, and ensuring content meets "
            "professional standards. Your review makes every article publication-ready."
        ),
        verbose=True,
        allow_delegation=False,
    )


def create_default_agents() -> List[Agent]:
    """Return the default agent team in execution order."""
    return [create_researcher(), create_writer(), create_editor()]
