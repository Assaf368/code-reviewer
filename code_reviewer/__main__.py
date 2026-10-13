import sys
from code_reviewer.agents.reviewer import build_reviwer

def main() -> None:

    if len(sys.argv) != 2:
        print("Usage: python -m code_reviewer <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    agent = build_reviwer()

    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Review the file {file_path}"}]
    })

    for message in result['messages']:
        message.pretty_print()





if __name__ == "__main__":
    main()