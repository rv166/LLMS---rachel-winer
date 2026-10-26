import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from openai import OpenAI
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SAFEAI_API_KEY")
BASE_URL = "https://safeai613.com/v1"

if not API_KEY:
    raise ValueError("API Key is missing! Please check your .env file.")

app = FastAPI(title="SafeAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# מבנה המייצג הודעה בודדת בהיסטוריה (מי שלח - user/assistant, ומה התוכן)
class Message(BaseModel):
    role: str
    content: str

# עדכון המודל כך שיקבל רשימת הודעות שלמה במקום מחרוזת אחת
class RequestModel(BaseModel):
    model: str = "gpt-4o-mini"
    messages: List[Message]

class ResponseModel(BaseModel):
    output_text: str
    model: str

httpx_client = httpx.Client(http2=True, verify=False)
client = OpenAI(base_url=BASE_URL, api_key=API_KEY, http_client=httpx_client)

@app.post("/generate", response_model=ResponseModel)
async def generate_content(request: RequestModel):
    try:
        # המרת רשימת ההודעות למבנה שה-API מצפה לקבל
        formatted_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        response = client.chat.completions.create(
            model=request.model,
            messages=formatted_messages
        )
        
        reply_text = response.choices[0].message.content

        return ResponseModel(
            output_text=reply_text,
            model=request.model
        )
    except Exception as e:
        print(f"Error details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)