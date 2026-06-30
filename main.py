from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agent import agent_executor
import uvicorn

# Initialize the API
app = FastAPI(
    title="Chidama Tech Agent API",
    description="Backend orchestration for the Chidama Tech interactive widget.",
    version="1.0.0"
)

# --- NEW CORS SETUP ---
# This tells your backend to safely accept messages from your Vite/React browser app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------

# Define the expected JSON payload from the frontend
class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_user_session"

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        # Wrap the user's input in a HumanMessage
        inputs = {"messages": [HumanMessage(content=req.message)]}
        
        # Invoke the LangGraph agent
        config = {"configurable": {"thread_id": req.thread_id}}
        response = agent_executor.invoke(inputs, config)
        
        # The agent's final answer is always the last message in the state
        latest_message = response["messages"][-1].content
        
        return {"response": latest_message}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run the server locally
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)