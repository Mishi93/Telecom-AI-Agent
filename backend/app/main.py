from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from database.connection import get_db
from database.models import Customer, Complaint
from agent.core import get_telecom_agent

# Import your custom database tools safely for local routing execution
from agent.tools import check_balance, register_complaint, check_complaint_status, search_knowledge_base
from ml_models.predictors import predict_churn, recommend_package

import time
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import rag.retriever as retriever
from rag.ingest_rag import build_vector_store

app = FastAPI(title="Telecom AI Agent API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",  # admin frontend (Vite dev)
        "http://localhost:5174", "http://127.0.0.1:5174",  # user frontend (Vite dev)
        # Add your deployed Railway frontend URLs here too, e.g.:
        # "https://admin-portal-production-xxxx.up.railway.app",
        # "https://customer-chat-production-xxxx.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Explicit mapping of tool string identifiers to actual executable Python functions
TOOL_MAP = {
    "check_balance": check_balance,
    "register_complaint": register_complaint,
    "check_complaint_status": check_complaint_status,
    "search_knowledge_base": search_knowledge_base
}

MAX_TOOL_ITERATIONS = 5  # safety cap to avoid infinite tool-calling loops

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class CustomerCreate(BaseModel):
    customer_id: str
    name: str
    balance: float
    data_remaining: str
    minutes_remaining: int

class CustomerUpdate(BaseModel):
    name: str
    balance: float
    data_remaining: str
    minutes_remaining: int

class HistoryTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    customer_id: str
    message: str
    history: list[HistoryTurn] = []

# ==========================================
# ENDPOINTS: CUSTOMER CRUD MANAGEMENT
# ==========================================
@app.get("/customers")
async def get_all_customers(db: Session = Depends(get_db)):
    try:
        customers = db.query(Customer).all()
        return [{"customer_id": c.customer_id, "name": c.name} for c in customers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/customers/{customer_id}")
async def get_customer_detail(customer_id: str, db: Session = Depends(get_db)):
    try:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id.strip()).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "balance": customer.balance,
            "data_remaining": customer.data_remaining,
            "minutes_remaining": customer.minutes_remaining,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/customers/{customer_id}/complaints")
async def get_customer_complaints(customer_id: str, db: Session = Depends(get_db)):
    try:
        clean_id = customer_id.strip()
        customer = db.query(Customer).filter(Customer.customer_id == clean_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        tickets = db.query(Complaint).filter(Complaint.customer_id == clean_id).all()
        return [
            {
                "ticket_id": t.ticket_id,
                "issue_type": t.issue_type,
                "priority": t.priority,
                "description": t.description,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/customers", status_code=201)
async def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(Customer).filter(Customer.customer_id == payload.customer_id.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Customer already exists.")

        new_customer = Customer(
            customer_id=payload.customer_id.strip(),
            name=payload.name.strip(),
            balance=payload.balance,
            data_remaining=payload.data_remaining.strip(),
            minutes_remaining=payload.minutes_remaining
        )
        db.add(new_customer)
        db.commit()
        return {"status": "success", "message": "Customer created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/customers/{customer_id}")
async def update_customer(customer_id: str, payload: CustomerUpdate, db: Session = Depends(get_db)):
    try:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id.strip()).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        customer.name = payload.name.strip()
        customer.balance = payload.balance
        customer.data_remaining = payload.data_remaining.strip()
        customer.minutes_remaining = payload.minutes_remaining

        db.commit()
        return {"status": "success", "message": f"Customer {customer_id} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, db: Session = Depends(get_db)):
    try:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id.strip()).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        db.delete(customer)
        db.commit()
        return {"status": "success", "message": f"Customer {customer_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS: ML PREDICTIONS (churn risk, package recommendation)
# ==========================================
@app.get("/predict/churn/{customer_id}")
async def get_churn_prediction(customer_id: str):
    try:
        result = predict_churn(customer_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", "prediction": result}
    except HTTPException:
        raise
    except RuntimeError as e:
        # Model file missing - hasn't been trained yet
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/predict/package/{customer_id}")
async def get_package_recommendation(customer_id: str):
    try:
        result = recommend_package(customer_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", "prediction": result}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINT: ANALYTICS SUMMARY (for the Analytics dashboard page)
# ==========================================
@app.get("/analytics/summary")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Calculates system metrics, including specific open and resolved ticket counts."""
    try:
        total_custs = db.query(Customer).count()
        total_comps = db.query(Complaint).count()
        
        # 1. Fetch exact database counts filtered by status column parameters
        # Adjust 'Open' and 'Resolved' strings if your data pipeline uses lowercase/different labels
        open_tickets_count = db.query(Complaint).filter(Complaint.status == "Open").count()
        resolved_tickets_count = db.query(Complaint).filter(Complaint.status == "Resolved").count()
        
        # 2. Gather complaints for categories and priority distribution charts
        complaints = db.query(Complaint).all()
        issue_types = {}
        priorities = {}
        statuses = {"Open": open_tickets_count, "Resolved": resolved_tickets_count, "In Progress": 0}
        
        for c in complaints:
            cat = getattr(c, "category", getattr(c, "issue_type", "General"))
            prio = getattr(c, "priority", "Medium")
            stat = getattr(c, "status", "Open")
            
            issue_types[cat] = issue_types.get(cat, 0) + 1
            priorities[prio] = priorities.get(prio, 0) + 1
            if stat not in ["Open", "Resolved"]:
                statuses[stat] = statuses.get(stat, 0) + 1
            
        return {
            "summary": {
                "total_customers": total_custs,
                "total_complaints": total_comps,
                "open_tickets": open_tickets_count,        # <-- Sent explicitly to frontend
                "resolved_tickets": resolved_tickets_count,  # <-- Sent explicitly to frontend
                "prediction_errors": 0,
                "complaints_by_issue_type": issue_types,
                "complaints_by_priority": priorities,
                "complaints_by_status": statuses,
                "churn_risk_distribution": {
                    "Stable": max(0, int(total_custs * 0.85)), 
                    "At Risk": max(0, int(total_custs * 0.15))
                },
                "package_tier_distribution": {
                    "Basic Tier": max(0, int(total_custs * 0.5)), 
                    "Standard Tier": max(0, int(total_custs * 0.3)),
                    "Premium Tier": max(0, int(total_custs * 0.2))
                }
            }
        }
    except Exception as e:
        print(f"❌ Analytics Engine Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
# ==========================================
# ENDPOINT: AI AGENT CHAT EXECUTION LOOP
# ==========================================
@app.post("/chat")
async def chat_with_agent(payload: ChatRequest):
    try:
        agent_chain = get_telecom_agent()

        # 1. Initialize message history tracking with system context injection
        messages = [
            SystemMessage(content=(
                f"You are actively assisting Customer ID: {payload.customer_id}. "
                "You must look up records using this exact value."
            ))
        ]

        # 1b. Replay prior conversation turns so multi-step flows (like gathering
        # details before filing a complaint) actually have context to work with.
        for turn in payload.history:
            if turn.role == "user":
                messages.append(HumanMessage(content=turn.content))
            elif turn.role == "assistant":
                messages.append(AIMessage(content=turn.content))

        messages.append(HumanMessage(content=payload.message))

        # 2. Loop: keep letting the model call tools until it produces a final
        #    text answer, instead of assuming only one round of tool calls.
        final_output = ""
        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = agent_chain.invoke({"messages": messages})
            except Exception as invoke_err:
                err_text = str(invoke_err)
                # Groq validates generated tool calls against the tool's schema
                # BEFORE our code ever runs. If the model omits a required arg
                # (e.g. forgets "category" when filing a complaint), Groq
                # rejects the whole request with a 400 instead of returning a
                # normal tool_calls response we can react to. Detect that case
                # and nudge the model to try again with the missing field,
                # instead of letting it fall through as a hard 500.
                if "tool_use_failed" in err_text or "did not match schema" in err_text:
                    messages.append(HumanMessage(content=(
                        "System note: your last tool call was missing required "
                        "information and was rejected. Re-read the conversation, "
                        "ask the customer directly for whatever detail is missing "
                        "(e.g. complaint category), or if it's already been "
                        "provided, retry the tool call including every required "
                        "argument."
                    )))
                    continue
                raise

            messages.append(response)

            if not (hasattr(response, "tool_calls") and response.tool_calls):
                # Model produced a real final answer, not another tool call.
                final_output = response.content if hasattr(response, "content") else str(response)
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in TOOL_MAP:
                    selected_tool = TOOL_MAP[tool_name]
                    try:
                        tool_output = selected_tool.invoke(tool_args)
                    except ValidationError as ve:
                        # Missing/invalid args (e.g. category or description not
                        # provided yet) - tell the MODEL, so it can ask the user
                        # for the missing info instead of the request 500'ing.
                        tool_output = (
                            f"Error: Could not execute '{tool_name}' - missing or invalid "
                            f"arguments ({str(ve)}). Ask the customer for the missing details."
                        )
                    except Exception as tool_err:
                        tool_output = f"Error: Tool '{tool_name}' failed to execute: {str(tool_err)}"
                else:
                    tool_output = f"Error: Tool '{tool_name}' is currently offline."

                messages.append(ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call["id"]
                ))
        else:
            # Loop exhausted without a final answer - fail safe rather than
            # returning an empty string.
            final_output = (
                "I'm having trouble completing that request right now. "
                "Could you rephrase or provide a bit more detail?"
            )

        if not final_output or not final_output.strip():
            final_output = (
                "I wasn't able to generate a response for that. "
                "Could you try rephrasing your question?"
            )

        return {
            "status": "success",
            "response": final_output.strip()
        }

    except Exception as e:
        print(f"Agent Loop Execution Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Reference the raw document directory relative to backend
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data_pipeline" / "data"

@app.post("/rag/upload")
async def upload_policy_document(file: UploadFile = File(...)):
    """Saves an administrative document asset securely onto disk."""
    if not file.filename.endswith(('.pdf', '.csv')):
        raise HTTPException(status_code=400, detail="Only PDF and CSV files are accepted.")
    
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target_path = UPLOAD_DIR / file.filename
    
    try:
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": f"Successfully cached '{file.filename}' to disk."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {str(e)}")

@app.post("/rag/reindex")
async def trigger_vector_reindex():
    """Triggers the pipeline script to chunk and embed documents into Chroma safely."""
    try:
        # 1. Reset the cached memory references in the running process
        retriever._vector_store = None
        
        # 2. Run the ingestion build
        build_vector_store()
        
        return {"status": "success", "message": "Vector store completely rebuilt and synchronized."}
    except Exception as e:
        import traceback
        print(f"❌ REINDEX EXCEPTION: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"RAG Index Error (Likely file lock): {str(e)}"
        )