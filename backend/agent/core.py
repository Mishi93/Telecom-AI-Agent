import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import your custom database tools safely
from agent.tools import check_balance, register_complaint, check_complaint_status, search_knowledge_base

# 0. Load variables from the .env file, resolved relative to this file's
#    location (not the current working directory). This file lives at
#    backend/agent/core.py, so .env at backend/.env is one level up.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# 1. Require the API key to come from the environment - never hardcode secrets.
#    (The previous fallback exposed a live Groq key in source control. Rotate
#    that key in the Groq console since it has been committed.)
if not os.environ.get("GROQ_API_KEY"):
    raise RuntimeError(
        "GROQ_API_KEY is not set. Set it as an environment variable "
        "(e.g. in a .env file loaded via python-dotenv) before starting the app."
    )

# 2. Initialize your central LLM model once
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# 3. Reference your available custom tool arrays
tools = [check_balance, register_complaint, check_complaint_status, search_knowledge_base]

# 4. Bind function schemas directly to the LLM engine natively
# This entirely removes external AgentExecutor or legacy graph wrapper requirements
llm_with_tools = llm.bind_tools(tools)

# 5. Build an atomic Prompt structure to securely track context windows
prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a professional customer support agent for our telecom company. "
        "You have access to a set of specialized database tools to look up account details, "
        "plus a knowledge base search tool for general plan/policy information. "
        "Always rely on your tools to fetch balances, remaining plan quotas, and complaint tickets. "
        "Use search_knowledge_base for general questions about plans, policies, or procedures that "
        "are not specific to this customer's own account - do not guess at company policy from "
        "memory. "
        "The register_complaint tool REQUIRES both 'category' and 'description' arguments - "
        "it will fail if either is missing. Before calling register_complaint, check the full "
        "conversation for both a clear category (e.g. Billing, Network, Technical, Other) and a "
        "description of the issue. If either is not yet known, do NOT call the tool - ask the "
        "customer a direct follow-up question for the missing piece first, then call the tool "
        "only once you have both. "
        "Provide direct, helpful answers without exposing raw JSON structures to the customer."
    )),
    MessagesPlaceholder(variable_name="messages"),
])

# 6. Compose your clean functional processing pipeline
_GLOBAL_AGENT_CHAIN = prompt | llm_with_tools

def get_telecom_agent():
    """
    Returns the pre-compiled native tool-calling chain instantly.
    Bypasses unstable library agent-builders and guarantees performance.
    """
    return _GLOBAL_AGENT_CHAIN