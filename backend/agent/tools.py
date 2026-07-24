import os
import uuid
import datetime
from langchain.tools import tool
from database.connection import SessionLocal
from database.models import Customer, Complaint  # Ensure both models are imported
from rag.retriever import query_knowledge_base as _query_knowledge_base

# ==========================================
# TOOL 1: CHECK PROFILE BALANCE & PLANS
# ==========================================
@tool
def check_balance(customer_id: str) -> str:
    """Retrieves current balance, remaining data package limits, and voice call minutes for a specific customer ID."""
    db = SessionLocal()
    try:
        clean_id = str(customer_id).strip()
        customer = db.query(Customer).filter(Customer.customer_id == clean_id).first()
        
        if not customer:
            return f"System Result: Customer account ID '{clean_id}' could not be located in the central ledger database."
        
        # Build an explicit, highly readable data layout for the LLM
        profile_summary = (
            f"Account Status for Customer {clean_id}:\n"
            f"- Account Holder Name: {customer.name}\n"
            f"- Current Outstanding Balance: ${customer.balance:.2f}\n"
            f"- Remaining High-Speed Data Plan Allocation: {customer.data_remaining}\n"
            f"- Available Voice Call Minutes Remaining: {customer.minutes_remaining} minutes"
        )
        return profile_summary
        
    except Exception as e:
        print(f"❌ DATABASE ERROR [check_balance]: {str(e)}")
        return f"System error reading balance metrics from database: {str(e)}"
    finally:
        db.close()

# ==========================================
# TOOL 2: LOOKUP COMPLAINT HISTORY / STATUS
# ==========================================
@tool
def check_complaint_status(customer_id: str) -> str:
    """Retrieves the history, descriptions, categories, and priority status of all support tickets or filed complaints for a specific customer ID."""
    db = SessionLocal()
    try:
        clean_id = str(customer_id).strip()
        # Explicit query against the complaints table
        tickets = db.query(Complaint).filter(Complaint.customer_id == clean_id).all()
        
        if not tickets:
            return f"System Result: No support tickets or filed complaints found for customer account '{clean_id}'."
        
        lines = [f"Found {len(tickets)} customer ticket registry row(s) for '{clean_id}':"]
        for idx, ticket in enumerate(tickets, 1):
            lines.append(
                f"Ticket #{idx}: [ID: {ticket.ticket_id}] [Category: {ticket.issue_type}] | "
                f"Description: {ticket.description} | "
                f"Priority: {ticket.priority} | Status: {ticket.status}"
            )
            
        return "\n".join(lines)
        
    except Exception as e:
        print(f"❌ DATABASE ERROR [check_complaint_status]: {str(e)}")
        return f"System error fetching complaint index rows: {str(e)}"
    finally:
        db.close()

# ==========================================
# TOOL 3: LODGE A NEW TICKET COMPLAINT
# ==========================================
@tool
def register_complaint(customer_id: str, category: str, description: str, priority: str = "Medium") -> str:
    """File or log a new technical complaint, support ticket, or billing issue in the database system for a customer."""
    db = SessionLocal()
    try:
        clean_id = str(customer_id).strip()
        
        # Verify the account actually exists first before creating a dangling orphan ticket
        customer_check = db.query(Customer).filter(Customer.customer_id == clean_id).first()
        if not customer_check:
            return f"System Rejection: Cannot register complaint. Customer ID '{clean_id}' does not exist."
        
        # ticket_id is required + unique on the complaints table but was never
        # being generated here, which caused every insert to fail with a
        # NOT NULL constraint error. Generate one: CMP-<year>-<random hex>.
        generated_ticket_id = f"CMP-{datetime.datetime.utcnow().year}-{uuid.uuid4().hex[:8].upper()}"

        # Instantiate a new record mapped straight to the table schema.
        # Note: the "category" the model/tool interface talks about maps to
        # the actual DB column "issue_type".
        new_ticket = Complaint(
            ticket_id=generated_ticket_id,
            customer_id=clean_id,
            issue_type=category.strip(),
            description=description.strip(),
            priority=priority.strip(),
            status="Open"
        )
        
        db.add(new_ticket)
        db.commit()
        
        return (
            f"Success System Result: New support ticket '{generated_ticket_id}' successfully filed "
            f"for Customer '{clean_id}' under category '{category.strip()}'. Priority set to "
            f"'{priority.strip()}'. Status: Open."
        )
        
    except Exception as e:
        db.rollback()
        print(f"❌ DATABASE ERROR [register_complaint]: {str(e)}")
        return f"System error writing new complaint ticket to database: {str(e)}"
    finally:
        db.close()

# ==========================================
# TOOL 4: SEARCH INTERNAL KNOWLEDGE BASE (RAG)
# ==========================================
@tool
def search_knowledge_base(query: str) -> str:
    """Searches internal telecom knowledge base documents (plan brochures, policy
    documents, FAQs, terms of service) for general information that is NOT
    tied to a specific customer's account. Use this for questions about what
    plans/packages exist, company policies, procedures, or general
    troubleshooting guidance - NOT for a customer's own balance, usage, or
    complaint history (use check_balance / check_complaint_status for those)."""
    try:
        return _query_knowledge_base(query)
    except RuntimeError as e:
        # Most likely: ingest_rag.py hasn't been run yet, so there's no
        # vector store on disk to query.
        print(f"❌ RAG ERROR [search_knowledge_base]: {str(e)}")
        return f"System Result: Knowledge base is not available right now: {str(e)}"
    except Exception as e:
        print(f"❌ RAG ERROR [search_knowledge_base]: {str(e)}")
        return f"System error searching knowledge base: {str(e)}"
    
@tool
def lookup_telecom_knowledge_base(query: str) -> str:
    """
    Useful when a customer asks questions about broadband plans, contract terms, 
    cancellation policies, hardware user guides, data caps, or generic FAQs. 
    Input should be a clean, semantic search string or question.
    """
    try:
        # Calls your existing vector similarity search routine
        return _query_knowledge_base(query, k=4)
    except Exception as e:
        return f"Error querying internal knowledge base documents: {str(e)}"