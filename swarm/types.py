from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from transitions import Machine
from typing import List, Callable, Union, Optional

# Third-party imports
from pydantic import BaseModel

AgentFunction = Callable[[], Union[str, "Agent", dict]]


class Agent(BaseModel):
    name: str = "Agent"
    model: str = "gpt-4o"
    instructions: Union[str, Callable[[], str]] = "You are a helpful agent."
    functions: List[AgentFunction] = []
    tool_choice: str = None
    parallel_tool_calls: bool = True

    # 상태 관리 추가
    def model_post_init(self, **kwargs):
        self.result = None  # 작업 결과 저장

        # 상태 정의 및 상태 머신 초기화
        self.states = ["Idle", "Running", "Completed", "Failed"]
        self.machine = Machine(model=self, states=self.states, initial="Idle")
        self.machine.add_transition("start_task", "Idle", "Running")
        self.machine.add_transition("complete_task", "Running", "Completed")
        self.machine.add_transition("fail_task", "Running", "Failed")
        self.machine.add_transition("reset_task", ["Completed", "Failed"], "Idle")

    def reset(self):
        """상태 초기화"""
        self.reset_task()

    async def run_task(self, handler: Callable, *args, **kwargs):
        """
        에이전트 작업 실행 및 상태 전환 관리.

        Args:
            handler (Callable): 작업을 처리할 함수.
            *args, **kwargs: 작업에 필요한 추가 인자.

        Returns:
            dict: 작업 결과.
        """
        try:
            # 작업 시작
            self.start_task()
            print(f"[{self.name}] Task started.")

            # 작업 실행 (핸들러 함수 호출)
            self.result = await handler(*args, **kwargs)

            # 작업 완료
            self.complete_task()
            print(f"[{self.name}] Task completed successfully.")

            return {"state": self.state, "result": self.result}
        
        except Exception as e:
            # 작업 실패
            self.fail_task()
            print(f"[{self.name}] Task failed with error: {e}")
            return {"state": self.state, "error": str(e)}
    
        
class Response(BaseModel):
    messages: List = []
    agent: Optional[Agent] = None
    context_variables: dict = {}


class Result(BaseModel):
    """
    Encapsulates the possible return values for an agent function.

    Attributes:
        value (str): The result value as a string.
        agent (Agent): The agent instance, if applicable.
        context_variables (dict): A dictionary of context variables.
    """

    value: str = ""
    agent: Optional[Agent] = None
    context_variables: dict = {}
