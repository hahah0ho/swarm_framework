from paper_rag import process_query as Rag
from tavily_search import search_on_web as Search
from custom_swarm import Swarm, Agent, CentralOrchestrator

import os

refine_prompt = """You are a highly skilled data refinement agent. Your primary task is to getting data by using functions and clean, preprocess, and refine raw data by removing noise, irrelevant information, and inconsistencies while maintaining the core integrity of the content. Ensure the refined data is structured, clear, and ready for further processing or analysis.
Given data: prev_data(by using get_prev_data function), search_data(by using get_search_data function)
When cleaning the data, adhere to the following guidelines:
1. **Noise Removal**:
   - Eliminate unrelated or redundant information such as advertisements, repetitive content, or non-essential text.
2. **Content Structuring**:
   - Organize the data into logical sections, separating titles, headers, and paragraphs appropriately.
   - Ensure each section is labeled or structured hierarchically if possible.
3. **Consistency**:
   - Standardize formatting (e.g., dates, numbers, and terminology) to ensure uniformity.
   - Remove conflicting or duplicated entries.
4. **Preserve Key Information**:
   - Retain all critical information that aligns with the primary purpose of the dataset.

Output the refined data in a structured format, such as JSON, Markdown"""

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
client = Swarm()

#Input
## 검색 타겟
target = ["Rag의 정의", "Rag의 활용", "Rag의 기술적 배경"]
## 발표 자료 가이드 라인
guideline = ""
## 기존 자료
prev_data = ""

#Layer_1 functions

def get_webdata_1():
  result = Search("모든 자료는 생성형 AI기술과 연관된 내용이어야 해."+target[0])
  return result
def get_webdata_2():
  return {"content":"Rag는 벡터 DB를 필요로한다."}
def get_webdata_3():
  # result = Search("모든 자료는 생성형 AI기술과 연관된 내용이어야 해."+target[2])
  return {"content":"Rag는 유사도를 기준으로 자료를 가져온다."}
#Layer_1 Agents
search_agent1 = Agent(
    name = "search_agent1",
    instructions="You are a helpful agent. Collecting the web data by using given function.",
    functions=[get_webdata_1]
)

search_agent2 = Agent(
    name = "search_agent2",
    instructions="You are a helpful agent. Collecting the web data by using given function.",
    functions=[get_webdata_2]
)
search_agent3 = Agent(
    name = "search_agent3",
    instructions="You are a helpful agent. Collecting the web data by using given function.",
    functions=[get_webdata_3]
)

#Layer_2 functions
def get_prev_data():
  result = prev_data
  return result

def get_search_data():
  return None

#Layer_2 Agents
refine_agent = Agent(
    name = "refine",
    instructions=refine_prompt,
    functions=[get_prev_data, get_search_data]
)

#Layer_3 Agents


#CentralOrchestrator
agent_results = {}

workflow = [
    {"name": "Step_1", "agents": ['search_agent1', 'search_agent2', 'search_agent3'], "description":"웹 검색을 통한 자료수집"},
    {"name": "Step_2", "agents": ["refine_agent"], "dependent_on": ['search_agent1', 'search_agent2', 'search_agent3'], "description":"prev_data와 search_data를 증복되거나 손실되는 내용 없이 정제"}
]

agents = [search_agent1, search_agent2, search_agent3, refine_agent]

messages = [{"role":"user", "content":"자료를 수집해서 강의자료를 만들어줘"}]

orchestrator = CentralOrchestrator(client, agent_results)
orchestrator.execute_workflow(workflow, agents, messages)
print(agent_results)