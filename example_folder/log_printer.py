import json
#로그데이터 출력 함수
def log_printer(log_data):
    for agent, response in log_data.items():
        if agent == "feedback":
            print('\033[35m'+f"UserFeedback: {response}"+'\033[0m')
            continue
        else:
            print('\033[35m'+"\n" + "-" * 50+'\033[0m')
            print('\033[35m'+f"Agent: {agent}"+'\033[0m')
            messages = response.messages
        for i, message in enumerate(messages, 1):
            print('\033[36m' + f"\n  Index [{i}]:" + '\033[0m')
            for key, value in message.items():
                if key == 'tool_calls' and isinstance(value, list):
                    print(f"    {key}:")
                    for tool_call in value:
                        print(f"      - {json.dumps(tool_call, indent=6)}")
                elif isinstance(value, dict):
                    print(f"    {key}: {json.dumps(value, indent=4)}")
                else:
                    print(f"    {key}: {value}")