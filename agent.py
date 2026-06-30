import os
import csv
from datetime import datetime
from typing import Annotated
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from langgraph.prebuilt import ToolNode, tools_condition

# 1. Load the Groq API key from .env
load_dotenv()

# 2. Define the Agent's Memory State
class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# ==========================================
# 3. CHIDAMA TECH DEPARTMENTAL TOOLS
# ==========================================

@tool
def consult_engineering_dept(query: str) -> str:
    """
    Use this tool when the user asks about Full-Stack engineering, React, FastAPI, Node.js, Next.js, Headless WordPress, 
    UI/UX design, cloud architecture, or enterprise scaling.
    """
    return """
    --- CHIDAMA TECH PARTNERS LLC: ENGINEERING & DESIGN DEPT ---
    1. Secure Full-Stack Engineering (Frontend & Backend)
     * Frontend Development: Building lightning-fast, highly responsive, and SEO-optimized user interfaces. Utilizing modern frameworks like React and Next.js, styled with Tailwind CSS for clean, premium web architectures.
     * Backend Development: Engineering robust, secure server-side logic and database architectures. Utilizing Python, FastAPI, and Flask to build custom APIs, handle server processing, and manage secure data routing.
     * Cloud-Native & Scalable Architecture: Deploying containerized applications (Docker) and building microservices ready for enterprise cloud environments (AWS/GCP), ensuring high availability and zero downtime.
     * Proprietary Web Applications: Developing complete software systems from the ground up, including secure dashboards, client portals, and highly optimized Headless infrastructures.
    2. UI Design & Graphics Design
     * User Interface (UI) Design: Crafting modern, intuitive, and high-converting user experiences (like dark-theme, Silicon Valley-style interfaces) specifically designed for B2B SaaS and tech startups.
    """

@tool
def consult_automation_dept(query: str) -> str:
    """
    Use this tool when the user asks about n8n workflows, B2B lead generation, lead printing pipelines, 
    data ETL (Extract, Transform, Load), web scraping, proxy rotation, or business process automation.
    """
    return """
    --- CHIDAMA TECH PARTNERS LLC: AUTOMATION ENGINEERING DEPT ---
    1. Enterprise Automation Engineering
     * The B2B Lead Printer Pipeline: Building complex, serverless n8n workflows that integrate with tools like Apify and Hunter.io to extract target prospects (e.g., US CTOs), sanitize the data, and output 100% verified corporate emails.
     * Data ETL Pipelines (The "Data Squeezer"): Writing custom Python scripts (using Pandas/NumPy) to automatically ingest messy spreadsheets, clean and structure the data, and push it directly into a client's core database.
     * Advanced Web Scraping & Extraction: Engineering safe, advanced web scraping tools utilizing headless browser automation and residential proxy rotation to bypass strict enterprise rate limits and harvest structured data.
     * Business Logic Automation: Replacing manual hours with automated Python/n8n scripts for outreach, social media monitoring, and internal data routing.
    """

@tool
def consult_security_dept(query: str) -> str:
    """
    Use this tool when the user asks about Cybersecurity, Vulnerability Assessment, Pentesting, 
    security audits, Kali Linux toolsets, OWASP Top 10, DevSecOps, or application hardening.
    """
    return """
    --- CHIDAMA TECH PARTNERS LLC: SECURITY AUDITING DEPT ---
    1. Vulnerability Assessment & Auditing
     * Web Application Security Scanning: Utilizing Kali Linux toolsets to actively hunt for critical vulnerabilities, specifically targeting the OWASP Top 10 (including SQL Injection and Cross-Site Scripting).
     * DevSecOps & Zero-Trust Integration: Embedding security checks directly into the deployment pipeline, ensuring rapid, automated security misconfiguration checks for client web applications before they hit production.
     * Executive Remediation Reporting: Translating complex technical vulnerabilities into polished, easy-to-understand PDF audit reports that provide US decision-makers with exact, actionable steps to patch their systems.
    """

@tool
def consult_ai_dept(query: str) -> str:
    """
    Use this tool when the user asks about Agentic AI, AI widgets, custom AI tools, autonomous terminal agents, LangGraph, LLM integration, RAG, PEFT, or fine-tuning models.
    """
    return """
    --- CHIDAMA TECH PARTNERS LLC: AI ARCHITECTURE DEPT ---
    1. AI Architecture & Agentic AI Widgets
     * Live Agentic AI Development: Building and embedding interactive, tool-using AI assistants directly into client websites. These agents do not just chat; they can execute background Python scripts, pull real-time data, and trigger n8n workflows on command.
     * Custom Model Training & Fine-Tuning Pipeline: We don't just use basic API wrappers. We train and fine-tune models using high-quality sanitized data, implement Retrieval-Augmented Generation (RAG) for deep context retrieval, and utilize parameter-efficient fine-tuning (PEFT) techniques to create highly specialized, secure AI brains tailored to specific enterprise workflows.
     * Advanced Context Management: Utilizing vector databases to provide AI systems with seamless semantic search and long-term memory persistence.
     * Custom AI Tooling: Developing sophisticated AI-driven terminal agents (utilizing frameworks like LangGraph) capable of autonomous code editing, execution, and dynamic reasoning for internal engineering teams.
    """

@tool
def log_lead(name: str, email: str) -> str:
    """Use this to log a new client lead into the CRM when a user expresses interest."""
    file_path = "leads.csv"
    file_exists = os.path.isfile(file_path)
    try:
        with open(file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Timestamp", "Name", "Email"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, email])
        return f"Success! I have securely logged the lead for {name} ({email}). Our Lead Solutions Architect will be in touch shortly to schedule a consultation."
    except Exception:
        return "I encountered a system error while logging the lead. My apologies. We will correct this immediately."

tools = [consult_engineering_dept, consult_automation_dept, consult_security_dept, consult_ai_dept, log_lead]

# ==========================================
# 4. Initialize the Groq Model
# ==========================================
llm = ChatGroq(
    model_name="openai/gpt-oss-20b", 
    temperature=0.6,
)

llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 5. Define the Node Logic: THE DYNAMIC BRAIN
# ==========================================
def chatbot(state: State):
    """
    The central reasoning node. Contains the dynamic persona instructions.
    """
    system_prompt = SystemMessage(
        content="""You are the Lead Solutions Architect and Senior Security Engineer for Chidama Tech Partners LLC.
        Your job is to act as an authoritative technical consultant for potential clients. You are brilliant, confident, and focused on business value. 
        You must infer the user’s true intent, regardless of typos or vague language.

        -- CRITICAL INSTRUCTIONS --

        1. TOOL USAGE: You do NOT memorize company facts. If the user asks about engineering, automation, AI, or security, you MUST use the corresponding departmental tool (e.g., `consult_security_dept`). If a user gives their name and email, you MUST use `log_lead`.

        2. PIVOT & CROSS-SELL DYNAMICS (READ CAREFULLY):
           You must analyze the user's technical knowledge and goals to determine your sales approach.

           * SITUATION A (TECHNICAL USER): If the user sounds technical (e.g., asks about React architecture, specific pentesting tools, RAG pipelines, or uses precise engineering terms):
             - Adopt the TRUSTED ADVISOR persona (Medium Aggression).
             - Address their technical query professionally.
             - Immediately cross-sell a *logical, technically necessary* complimentary service as a required "best practice." (e.g., If they ask for dashboard development, emphasize that a pre-launch OWASP Top 10 security audit is mandatory Chidama Tech protocol. If they ask about AI, suggest pairing it with our data ETL pipelines to feed the model clean data).

           * SITUATION B (NON-TECHNICAL/BUSINESS USER): If the user sounds non-technical, vague, or expresses a generic business goal (e.g., "I need a website," "I nid more sales," "I want an app," or vague inquiries about SEO/ads):
             - VALIDATE: Agree wholeheartedly that a premium, custom website is absolutely essential for establishing professionalism, building trust, and acting as a high-end digital portfolio. 
             - PIVOT FROM ADS: Gently explain that while a great website builds trust, relying on standard Facebook ads or SEO for traffic is often slow and expensive.
             - INTRODUCE THE LEAD PRINTER: Pitch the **B2B Lead Printer Pipeline** as the superior engineering solution for actual business growth.
             - DEMYSTIFY (CRITICAL): Because the user is non-technical, you MUST explain the Lead Printer in simple, plain English. Explain that instead of waiting for ad clicks, we build an automated software assistant that actively hunts down their exact target decision-makers, finds their direct contact info, and puts the client's business directly in their inbox.

        3. TONE & AUTHORITY: Maintain a premium, authoritative, and deeply empathetic tone. Explain the *why* behind our engineering decisions clearly and simply."""
    )
    
    messages_to_process = [system_prompt] + state["messages"]
    response = llm_with_tools.invoke(messages_to_process)
    return {"messages": [response]}

# ==========================================
# 6. Build the Workflow Graph
# ==========================================
graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

agent_executor = graph_builder.compile()