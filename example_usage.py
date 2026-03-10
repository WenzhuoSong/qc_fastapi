"""
CrewAI + FastAPI Usage Examples
Demonstrates how to call APIs to execute agent tasks
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"


def example_execute_crew():
    """Example: Execute Crew task"""
    
    url = f"{BASE_URL}/crew/execute"
    
    payload = {
        "topic": "Applications of Artificial Intelligence in Healthcare",
        # Optional: Custom agent configuration
        # "agents_config": [...],
        # "tasks_config": [...],
    }
    
    print("🚀 Sending request to CrewAI service...")
    print(f"Topic: {payload['topic']}")
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Task executed successfully!")
            print(f"Execution time: {result.get('execution_time', 'N/A')} seconds")
            print("\n📄 Output result:")
            print("-" * 50)
            print(result.get('result', 'No output'))
            print("-" * 50)
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.Timeout:
        print("⏱️ Request timed out, task may still be running in background")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def example_get_crew_info():
    """Example: Get Crew information"""
    
    url = f"{BASE_URL}/crew/info"
    
    print("📋 Getting Crew configuration information...")
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            info = response.json()
            print(f"\n🎭 Crew Name: {info['name']}")
            print(f"📝 Description: {info['description']}")
            print(f"\n👥 Agent Team ({len(info['agents'])} agents):")
            
            for i, agent in enumerate(info['agents'], 1):
                print(f"\n  {i}. {agent['role']}")
                print(f"     Goal: {agent['goal']}")
            
            print(f"\n📋 Task Workflow ({len(info['tasks'])} tasks):")
            for i, task in enumerate(info['tasks'], 1):
                print(f"\n  {i}. {task['expected_output']}")
        else:
            print(f"❌ Request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def example_task_management():
    """Example: Task management"""
    
    # Create task
    create_url = f"{BASE_URL}/tasks/"
    
    payload = {
        "name": "Research Task Example",
        "description": "Research latest advances in quantum computing",
        "agent_role": "Researcher",
        "expected_output": "A research report on quantum computing",
    }
    
    print("📝 Creating new task...")
    
    try:
        response = requests.post(create_url, json=payload)
        
        if response.status_code == 200:
            task = response.json()
            print(f"✅ Task created successfully: {task['id']}")
            
            # Get task list
            list_url = f"{BASE_URL}/tasks/"
            response = requests.get(list_url)
            
            if response.status_code == 200:
                tasks = response.json()
                print(f"\n📋 Current task list ({len(tasks)} tasks):")
                for t in tasks:
                    print(f"  - {t['id']}: {t['name']} ({t['status']})")
        else:
            print(f"❌ Creation failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    print("=" * 60)
    print("CrewAI + FastAPI Usage Examples")
    print("=" * 60)
    
    # Select example to run
    import sys
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        print("\nAvailable examples:")
        print("1. crew_info - Get Crew information")
        print("2. execute - Execute Crew task")
        print("3. tasks - Task management example")
        print("\nUsage: python example_usage.py [option]")
        choice = input("\nPlease select (1/2/3): ").strip()
    
    print()
    
    if choice == "1" or choice == "crew_info":
        example_get_crew_info()
    elif choice == "2" or choice == "execute":
        example_execute_crew()
    elif choice == "3" or choice == "tasks":
        example_task_management()
    else:
        print("Invalid option")
