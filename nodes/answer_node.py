from app.llm import get_llm
from utils.console import node_start, node_detail, node_end
import re

_MAX_HISTORY_TURNS = 10


def _clean_plain_text(answer: str) -> str:
    answer = re.sub(r"\*\*(.*?)\*\*", r"\1", answer)
    answer = re.sub(r"__(.*?)__", r"\1", answer)
    answer = re.sub(r"^[\s>*\-]+", "", answer, flags=re.MULTILINE)
    answer = re.sub(r"\s+", " ", answer)
    return answer.strip()

def _build_prompt(state: dict) -> str:
    # Build conversation context from chat history stored in SQLite
    history = state.get("chat_history") or []
    recent = history[-_MAX_HISTORY_TURNS:]
    convo = "\n".join(f"{t['role']}:{t['content']}" for t in recent)
    question = state.get("question") or state.get("user_question", "")

    instruction = f"""
    You are a senior data analyst.

    Question:
    {question}

    Query result:
    {state['result']}

    Use only the query result above. Do not add facts, explanations, or numbers that are not present in the query result.
    If the query result is empty or insufficient, say that the connected database result does not contain enough information.
    Return one concise plain-text answer.
    Do not use Markdown, bullets, bold text, asterisks, headings, or numbered sections.
    Include the most important finding and one practical business insight when useful.
"""
    return f"{convo}\n\n{instruction}" if convo else instruction

def answer_node(state: dict) -> dict:
    """Generate a concise answer from query results.

    Conversation context is carried in ``state['chat_history']`` which is
    loaded from SQLite before the graph is invoked.
    """
    node_start("answer_node", "Generating insights from query results")

    if state.get("response_mode") == "chart":
        state["answer"] = ""
        node_detail("answer_node", "Skip", "Response mode is chart-only.")
        node_end("answer_node", "Skipped answer generation")
        return state

    question = state.get("question") or state.get("user_question", "")
    node_detail("answer_node", "Question", question)

    result_rows = state.get("result", {}).get("rows", [])
    node_detail("answer_node", "Input data", f"{len(result_rows)} row(s) from query")

    prompt = _build_prompt(state)

    if not result_rows:
        assistant_msg = "The connected database returned no matching rows, so there is not enough data to answer this exactly."
    else:
        response = get_llm(state.get("gemini_api_key")).invoke(prompt)
        assistant_msg = _clean_plain_text(response.content)

    state['answer'] = assistant_msg

    node_detail("answer_node", "Answer", assistant_msg)
    node_end("answer_node", "Analysis complete")

    return state
