"""
CrewAI Task Definitions

Each function returns a configured Task instance.
Keep agent definitions in agents.py — this file only describes *what* to do.
"""

from typing import List

try:
    from crewai import Task
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

    class Task:                                           # type: ignore[no-redef]
        def __init__(self, description="", expected_output="", agent=None, context=None):
            self.description = description
            self.expected_output = expected_output
            self.agent = agent
            self.context = context or []


def create_research_task(researcher) -> Task:
    return Task(
        description=(
            "Conduct in-depth research on the topic '{topic}'.\n\n"
            "Requirements:\n"
            "1. Collect core concepts and key information about this topic\n"
            "2. Identify relevant latest developments and trends\n"
            "3. Identify main viewpoints and controversies\n"
            "4. Organize into a structured research report\n\n"
            "Output format:\n"
            "- Topic overview\n"
            "- Key points (at least 5)\n"
            "- Relevant data and facts\n"
            "- Suggested information sources"
        ),
        expected_output="A detailed research report containing core information and key findings about the topic",
        agent=researcher,
    )


def create_writing_task(writer, research_task: Task) -> Task:
    return Task(
        description=(
            "Based on the research report, write a high-quality article about '{topic}'.\n\n"
            "Requirements:\n"
            "1. Use information from the research report\n"
            "2. Clear article structure with introduction, body, and conclusion\n"
            "3. Language should be accessible and suitable for general readers\n"
            "4. Length between 800-1200 words\n"
            "5. Add appropriate headings and subheadings\n\n"
            "Note: Ensure content accuracy, do not add unverified information."
        ),
        expected_output="A well-structured, content-rich article",
        agent=writer,
        context=[research_task],
    )


def create_editing_task(editor, writing_task: Task) -> Task:
    return Task(
        description=(
            "Review and improve the article about '{topic}'.\n\n"
            "Requirements:\n"
            "1. Check factual accuracy\n"
            "2. Improve language expression and flow\n"
            "3. Ensure logical structure is sound\n"
            "4. Correct grammar and spelling errors\n"
            "5. Provide final polished version\n\n"
            "Output:\n"
            "- Modified final article\n"
            "- Summary of changes made"
        ),
        expected_output="Final version of article after editorial review, with change summary",
        agent=editor,
        context=[writing_task],
    )


def create_default_tasks(agents: list) -> List[Task]:
    """Build the default sequential task chain from a list of agents.

    Expected order: [researcher, writer, editor].
    """
    researcher, writer, editor = agents[0], agents[1], agents[2]
    research = create_research_task(researcher)
    writing = create_writing_task(writer, research)
    editing = create_editing_task(editor, writing)
    return [research, writing, editing]
