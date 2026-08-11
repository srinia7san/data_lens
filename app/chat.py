import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.graph import graph
from utils.console import pipeline_start, pipeline_end

def run_chat():
    print("=" * 80)
    print("🧠 DATA ANALYST INTERACTIVE TERMINAL")
    print("Type 'exit' or 'quit' to close.")
    print("=" * 80)

    chat_history: list[dict[str, str]] = []

    while True:
        try:
            question = input("\n📝 Ask a question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        
        if not question:
            continue

        pipeline_start(question)
        
        state_input = {
            "question": question,
            "connection_string": os.getenv("DATABASE_URL"),
            "db_dialect": "PostgreSQL",
            "chat_history": chat_history,
        }

        try:
            result = graph.invoke(state_input)
            pipeline_end(result)
            
            # Append this turn to the running history for next iteration
            chat_history.append({"role": "user", "content": question})
            final_answer = result.get("answer")
            if final_answer:
                chat_history.append({"role": "assistant", "content": final_answer})
                print("\n" + "=" * 40)
                print("🤖 ANSWER:")
                print(final_answer)
                print("=" * 40)
                
        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")

if __name__ == "__main__":
    run_chat()

