from example_folder.tavily_search import search_on_web_1 as Search1
from example_folder.tavily_search import search_on_web_2 as Search2
from example_folder.prompts import topic_prompt, objective_prompt, search_prompt, validate_prompt, writing_prompt, criticize_prompt
from example_folder.log_printer import log_printer
from custom_swarm import Swarm, Agent, CentralOrchestrator
import json
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = Swarm()
agent_results = {}

def transfer_to_topic():
    return topic_agent
  
def transfer_to_objective():
    return objective_agent

def get_objective_data() -> str:
    result = agent_results['objective_agent'].messages[-1]['content']
    return result

def web_search_1(query: str) -> json:
    """Search `query` on the web(google) and return the results"""
    result = Search1(query)
    return result
  
def web_search_2(query: str) -> json:
    """Search `query` on the web(naver) and return the results"""
    result = Search2(query)
    return result

def transfer_to_validate_agent1():
    return validate_agent_1

def transfer_to_validate_agent2():
    return validate_agent_2

def transfer_to_search_agent1():
    return search_agent1

def transfer_to_search_agent2():
    return search_agent2

def get_writing_data():
    research_objective = agent_results['objective_agent'].messages[-1]['content']
    related_data1 = agent_results['validate_agent_1'].messages[-1]['content']
    related_data2 = agent_results['validate_agent_2'].messages[-1]['content']
    result = {
        "research_objective" : agent_results['objective_agent'].messages[-1]['content'],
        "related_data1" : agent_results['validate_agent_1'].messages[-1]['content'],
        "related_data2" : agent_results['validate_agent_2'].messages[-1]['content']
    }
    return result

def transfer_to_writing_agent():
    """transfer to Writing Agent for writing report"""
    # 보고서 작성을 위해 Writing Agent로 전환
    return writing_agent

def transfer_to_criticize_agent():
    """transfer to Critic Agent for making improvements on draft report"""
    # 초안 보고서 개선을 위해 Critic Agent로 전환
    return criticize_agent

#Layer 1 Agents
topic_agent = Agent(
    name = "topic_agent",
    instructions=topic_prompt,
    functions=[transfer_to_objective]
)

objective_agent = Agent(
    name = "objective_agent",
    instructions=objective_prompt,
    functions=[transfer_to_topic]
)

#Layer 2 Agents
search_agent1 = Agent(
    name = "search_agent1",
    instructions=search_prompt,
    functions=[get_objective_data, web_search_1, transfer_to_validate_agent1]
)

search_agent2 = Agent(
    name = "search_agent2",
    instructions=search_prompt,
    functions=[get_objective_data, web_search_2, transfer_to_validate_agent2]
)

validate_agent_1 = Agent(
  name = "validate_agent_1",
  instructions=validate_prompt,
  functions=[get_objective_data, transfer_to_search_agent1]
)

validate_agent_2 = Agent(
  name = "validate_agent_2",
  instructions=validate_prompt,
  functions=[get_objective_data, transfer_to_search_agent2]
)

writing_agent = Agent(
  name = "writing_agent",
  instructions=writing_prompt,
  functions=[transfer_to_criticize_agent, get_writing_data]
)

criticize_agent = Agent(
  name = "criticize_agent",
  instructions=criticize_prompt,
  functions=[transfer_to_writing_agent]
)


#CentralOrchestrator
workflow = [
    {"name": "Layer_1", "agents": ['topic_agent'], "description":"연구의 주제와 세부 목적을 선정하고 구체화 해."},
    {"name": "Layer_2", "agents": ["search_agent1", "search_agent2"], "dependent_on": ["objective_agent"], "description":"연구 목적과 연구 질문에 필요한 정보들을 수집해."},
    {"name": "Layer_3", "agents": ["writing_agent"], "dependent_on": ["objective_agent", "validate_agent1", "validate_agent2"], "description":"주어진 정보와 연구 목적을 바탕으로 보고서 혹은 논문을 작성해."}
]

agents = [topic_agent, search_agent1, search_agent2, writing_agent]

user_query = input()
messages = [{"role":"user", "content":user_query}]

orchestrator = CentralOrchestrator(client, agent_results)
orchestrator.execute_workflow(workflow, agents, messages)

log_printer(agent_results)