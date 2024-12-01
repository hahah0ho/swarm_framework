# Standard library imports
import copy
import json
from collections import defaultdict
from typing import List, Callable, Union, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

# Package/library imports
from openai import OpenAI


# Local imports
from .util import function_to_json, debug_print, merge_chunk
from .types import (
    Agent,
    AgentFunction,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    Function,
    Response,
    Result,
)

__CTX_VARS_NAME__ = "context_variables"


class Swarm:
    def __init__(self, client=None):
        if not client:
            client = OpenAI()
        self.client = client
        self.task_results = []

    def get_chat_completion(
        self,
        agent: Agent,
        history: List,
        context_variables: dict,
        model_override: str,
        stream: bool,
        debug: bool,
    ) -> ChatCompletionMessage:
        context_variables = defaultdict(str, context_variables)
        instructions = (
            agent.instructions(context_variables)
            if callable(agent.instructions)
            else agent.instructions
        )
        messages = [{"role": "system", "content": instructions}] + history
        debug_print(debug, "Getting chat completion for...:", messages)

        tools = [function_to_json(f) for f in agent.functions]
        # hide context_variables from model
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop(__CTX_VARS_NAME__, None)
            if __CTX_VARS_NAME__ in params["required"]:
                params["required"].remove(__CTX_VARS_NAME__)

        create_params = {
            "model": model_override or agent.model,
            "messages": messages,
            "tools": tools or None,
            "tool_choice": agent.tool_choice,
            "stream": stream,
        }

        if tools:
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls

        return self.client.chat.completions.create(**create_params)

    def handle_function_result(self, result, debug) -> Result:
        match result:
            case Result() as result:
                return result

            case Agent() as agent:
                return Result(
                    value=json.dumps({"assistant": agent.name}),
                    agent=agent,
                )
            case _:
                try:
                    return Result(value=str(result))
                except Exception as e:
                    error_message = f"Failed to cast response to string: {result}. Make sure agent functions return a string or Result object. Error: {str(e)}"
                    debug_print(debug, error_message)
                    raise TypeError(error_message)

    def handle_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        context_variables: dict,
        debug: bool,
    ) -> Response:
        function_map = {f.__name__: f for f in functions}
        partial_response = Response(
            messages=[], agent=None, context_variables={})

        for tool_call in tool_calls:
            name = tool_call.function.name
            # handle missing tool case, skip to next tool
            if name not in function_map:
                debug_print(debug, f"Tool {name} not found in function map.")
                partial_response.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "tool_name": name,
                        "content": f"Error: Tool {name} not found.",
                    }
                )
                continue
            args = json.loads(tool_call.function.arguments)
            debug_print(
                debug, f"Processing tool call: {name} with arguments {args}")

            func = function_map[name]
            # pass context_variables to agent functions
            if __CTX_VARS_NAME__ in func.__code__.co_varnames:
                args[__CTX_VARS_NAME__] = context_variables
            raw_result = function_map[name](**args)

            result: Result = self.handle_function_result(raw_result, debug)
            partial_response.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "tool_name": name,
                    "content": result.value,
                }
            )
            partial_response.context_variables.update(result.context_variables)
            if result.agent:
                partial_response.agent = result.agent

        return partial_response

    def run_and_stream(
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
    ):
        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns:

            message = {
                "content": "",
                "sender": agent.name,
                "role": "assistant",
                "function_call": None,
                "tool_calls": defaultdict(
                    lambda: {
                        "function": {"arguments": "", "name": ""},
                        "id": "",
                        "type": "",
                    }
                ),
            }

            # get completion with current history, agent
            completion = self.get_chat_completion(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=True,
                debug=debug,
            )

            yield {"delim": "start"}
            for chunk in completion:
                delta = json.loads(chunk.choices[0].delta.json())
                if delta["role"] == "assistant":
                    delta["sender"] = active_agent.name
                yield delta
                delta.pop("role", None)
                delta.pop("sender", None)
                merge_chunk(message, delta)
            yield {"delim": "end"}

            message["tool_calls"] = list(
                message.get("tool_calls", {}).values())
            if not message["tool_calls"]:
                message["tool_calls"] = None
            debug_print(debug, "Received completion:", message)
            history.append(message)

            if not message["tool_calls"] or not execute_tools:
                debug_print(debug, "Ending turn.")
                break

            # convert tool_calls to objects
            tool_calls = []
            for tool_call in message["tool_calls"]:
                function = Function(
                    arguments=tool_call["function"]["arguments"],
                    name=tool_call["function"]["name"],
                )
                tool_call_object = ChatCompletionMessageToolCall(
                    id=tool_call["id"], function=function, type=tool_call["type"]
                )
                tool_calls.append(tool_call_object)

            # handle function calls, updating context_variables, and switching agents
            partial_response = self.handle_tool_calls(
                tool_calls, active_agent.functions, context_variables, debug
            )
            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            if partial_response.agent:
                active_agent = partial_response.agent

        yield {
            "response": Response(
                messages=history[init_len:],
                agent=active_agent,
                context_variables=context_variables,
            )
        }
        
    def initialize_agent_state(self, agents: List[Agent]):
        """에이전트 상태를 초기화."""
        self.agent_states = {agent.name: "Idle" for agent in agents}

    def update_agent_state(self, agent: Agent, state: str):
        """에이전트 상태 업데이트."""
        self.agent_states[agent.name] = state
        print(f"[Swarm] Agent {agent.name} state updated to {state}.")


    def run(
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        stream: bool = False,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
    ) -> Response:
        try:
            # 에이전트 상태를 Running으로 업데이트
            self.update_agent_state(agent, "Running")

            active_agent = agent
            context_variables = copy.deepcopy(context_variables)
            history = copy.deepcopy(messages)
            init_len = len(messages)

            while len(history) - init_len < max_turns and active_agent:
                # get completion with current history, agent
                completion = self.get_chat_completion(
                    agent=active_agent,
                    history=history,
                    context_variables=context_variables,
                    model_override=model_override,
                    stream=stream,
                    debug=debug,
                )
                message = completion.choices[0].message
                debug_print(debug, "Received completion:", message)
                message.sender = active_agent.name
                history.append(
                    json.loads(message.model_dump_json())
                )  # to avoid OpenAI types (?)

                if not message.tool_calls or not execute_tools:
                    debug_print(debug, "Ending turn.")
                    break

                # handle function calls, updating context_variables, and switching agents
                partial_response = self.handle_tool_calls(
                    message.tool_calls, active_agent.functions, context_variables, debug
                )
                history.extend(partial_response.messages)
                context_variables.update(partial_response.context_variables)
                if partial_response.agent:
                    active_agent = partial_response.agent

            # 작업이 성공적으로 완료되었으므로 상태를 Completed로 업데이트
            self.update_agent_state(agent, "Completed")
            return Response(
                messages=history[init_len:],
                agent=active_agent,
                context_variables=context_variables,
            )

        except Exception as e:
            # 작업 중 실패 시 상태를 Failed로 업데이트
            self.update_agent_state(agent, "Failed")
            debug_print(debug, f"Agent {agent.name} failed with error: {e}")
            raise e
        
        
    
    def run_parallel_agents(
        self,
        agents: List[Agent],
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        debug: bool = False,
    ) -> List[Response]:
        """
        여러 에이전트를 병렬로 실행하며 상태를 추적.

        Args:
            agents (List[Agent]): 병렬로 실행할 에이전트 리스트.
            messages (List): 에이전트에 전달할 메시지 히스토리.
            context_variables (dict): 공유 컨텍스트 변수.
            model_override (str): 모델 이름을 오버라이드할 옵션.
            debug (bool): 디버그 모드 활성화 여부.

        Returns:
            List[Response]: 각 에이전트 실행 결과 리스트.
        """
        # 상태 초기화
        self.initialize_agent_state(agents)

        results = []
        with ThreadPoolExecutor() as executor:
            # 에이전트별 Future 생성
            future_to_agent = {
                executor.submit(
                    self.run,  # 기존의 단일 실행 메서드를 호출
                    agent,
                    messages,
                    context_variables.copy(),
                    model_override,
                    False,  # stream 비활성화
                    debug,
                ): agent
                for agent in agents
            }

            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    response = future.result()
                    results.append(response)
                    debug_print(debug, f"Agent {agent.name} completed successfully.")
                except Exception as e:
                    debug_print(debug, f"Agent {agent.name} failed with error: {e}")

        return results
    

class CentralOrchestrator:
    def __init__(self, swarm: Swarm, agent_results: Dict[str, Any]):
        """
        중앙 오케스트레이터 초기화.

        Args:
            swarm (Swarm): 에이전트를 관리하는 Swarm 인스턴스.
            agent_results (Dict[str, Any]): 에이전트 결과를 저장할 외부 데이터 구조.
        """
        self.swarm = swarm
        self.agent_states: Dict[str, str] = {}  # 각 에이전트 상태 저장
        self.agent_results = agent_results  # 외부 제공 데이터 구조를 참조
        self.failed_agents: List[str] = []      # 실패한 에이전트 목록

    def initialize_states(self, agents: List[Agent]):
        """
        모든 에이전트의 초기 상태를 설정.
        """
        self.swarm.initialize_agent_state(agents)
        self.agent_states = self.swarm.agent_states

    def update_agent_state_and_result(self, agent_name: str, state: str, result: Any = None):
        """
        에이전트 상태와 결과를 업데이트.

        Args:
            agent (Agent): 상태를 업데이트할 에이전트.
            state (str): 에이전트의 새로운 상태.
            result (Any): 에이전트 작업 결과 또는 에러 메시지.
        """
        self.agent_states[agent_name] = state
        self.agent_results[agent_name] = result  # 외부 데이터 구조에 결과 저장
        print(f"[Orchestrator] Agent {agent_name} state updated to {state}.")
        if result:
            print(f"[Orchestrator] Agent {agent_name} result: {result.messages[-1]['content']}")
            
    def get_user_feedback(self, step_name: str):
        """
        사용자로부터 다음 스텝 진행 여부와 피드백을 입력받습니다.

        Args:
            step_name (str): 현재 스텝 이름.

        Returns:
            str: 'next' 또는 'retry'.
        """
        while True:
            print(f"\n[Orchestrator] Step '{step_name}' completed.")
            print("Options:")
            print("1. Proceed to the next step.")
            print("2. Retry the current step with feedback.")
            user_input = input("Enter your choice (1 or 2): ").strip()

            if user_input == "1":
                return "next"
            elif user_input == "2":
                feedback = input("Enter your feedback for retrying this step: ").strip()
                print(f"[Orchestrator] Received feedback: {feedback}")
                self.agent_results["feedback"] = feedback  # 저장 (필요시 추가 활용)
                return "retry"
            else:
                print("[Orchestrator] Invalid input. Please enter 1 or 2.")

    def execute_workflow(self, workflow: List[Dict], agents: List[Agent], messages: List):
        """
        워크플로우를 실행하며 상태 및 결과를 관리.
        이전 스텝의 결과를 다음 스텝으로 전달.

        Args:
            workflow (List[Dict]): 작업 단계와 종속성을 정의한 워크플로우.
            agents (List[Agent]): 실행할 에이전트 목록.
            messages (List): 초기 메시지.
        """
        # 초기 상태 설정
        self.initialize_states(agents)

        for step in workflow:
            step_name = step["name"]
            dependent_on = step.get("dependent_on", [])
            if step_name == workflow[0]["name"]:
                first_query = messages[0]["content"]+","+step["description"]
                step_messages = [{"role":"user", "content":first_query}]
            else:
                step_messages = [{"role":"user", "content":step["description"]}]
            messages = step_messages
            while True:

                print(f"[Workflow] Executing step: {step_name}")

                # 의존성이 있는 경우, 해당 에이전트들의 결과를 context_variables에 병합
                if dependent_on:
                    print(f"[Workflow] Step {step_name} depends on: {dependent_on}")
                    dependent_results = {
                        agent_name: self.agent_results[agent_name]
                        for agent_name in dependent_on
                        if agent_name in self.agent_results
                    }
                    # 의존성 결과를 context_variables에 추가
                    context_variables = {"dependent_results": dependent_results}
                else:
                    context_variables = {}

                # 현재 스텝에 해당하는 에이전트 선택
                step_agents = [agent for agent in agents if agent.name in step["agents"]]

                # 에이전트 병렬 실행 및 결과 수집
                results = self.swarm.run_parallel_agents(
                    step_agents,
                    messages,
                    context_variables  # 의존성 결과를 전달
                )

                # 에이전트 상태 및 결과 업데이트
                for result in results:
                    agent_name = result.agent.name
                    state = "Completed" if result.messages else "Failed"
                    self.update_agent_state_and_result(agent_name, state, result)
                        
                # 사용자 입력 처리
                user_decision = self.get_user_feedback(step_name)
                if user_decision == "retry":
                    print(f"[Orchestrator] Retrying step: {step_name}")
                    feedback = self.agent_results.get("feedback", "No feedback provided.")
                    messages.append({"role": "user","content": f"{step_messages}\nFeedback: {feedback}"})
                    continue  # 현재 스텝 다시 실행
                elif user_decision == "next":
                    print(f"[Orchestrator] Proceeding to the next step.")
                    break

        print("[Orchestrator] Workflow execution completed.")