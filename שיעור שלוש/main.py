from __future__ import annotations

import json
import os
import ssl
from datetime import date
from pathlib import Path
from typing import Any

import httpx2
from dotenv import load_dotenv
from openai import OpenAI


MAX_TURNS = 5

SYSTEM_PROMPT = """
את/ה סוכן/ת CLI שמכין/ה למשתמש/ת לוח עבודה למשימות של היום.

תהליך העבודה:
1. בתחילת הכנת הלוח, הפעל/י את read_tasks כדי לקרוא את המשימות הפתוחות של היום.
   אם כבר הוצג לוח בשיחה והמשתמש/ת עונה לשאלת המשך, המשך/י מאותה נקודה ואל
   תקרא/י שוב את המשימות, אלא אם המשתמש/ת ביקש/ה במפורש לוח חדש או עדכון.
2. הצג/י טבלה בעברית עם עמודות: משימה, דחיפות, זמן משוער והסבר קצר.
   הערך/י דחיפות לפי priority ו-due_date. הערך/י זמן בדקות לפי תיאור המשימה,
   וציין/י שזו הערכה בלבד. אם חסר מידע מהותי, שאל/י שאלה ממוקדת באמצעות ask_user
   במקום להמציא פרטים.
3. לאחר הצגת הטבלה, שאל/י באמצעות ask_user אם המשתמש/ת רוצה לשמור אותה בקובץ.
   אל תציג/י את שאלת האישור כהודעת טקסט בלבד: הפעל/י את הכלי כדי לקבל תשובה.
4. רק אם התשובה חיובית, שאל/י באמצעות ask_user איזה פורמט לבחור:
   TXT, CSV או JSON. גם את שאלת הפורמט יש להפנות באמצעות הכלי.
5. לאחר שהמשתמש/ת בחר/ה פורמט נתמך, צור/י תוכן מתאים והפעל/י create_task_file.
   אל תיצור/י קובץ בלי אישור מפורש ובחירת פורמט. לאחר יצירתו, דווח/י על הנתיב
   שהכלי החזיר.

אם אין משימות להיום, אמור/י זאת בבירור ואל תמציא/י משימות. אפשר להציע לשמור
את ההודעה הזו רק אם היא כוללת תוכן שימושי למשתמש/ת.
"""

def read_tasks() -> list[dict[str, Any]]:
    """Return open tasks scheduled for today from the mock JSON file."""
    tasks_path = Path(__file__).with_name("tasks.json")
    with tasks_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError("tasks.json must contain a 'tasks' list.")

    tasks = data["tasks"]
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task in tasks.json must be an object.")
        if "scheduled_for" not in task or "status" not in task:
            raise ValueError("Each task must include 'scheduled_for' and 'status'.")

    today = date.today().isoformat()
    return [
        task
        for task in tasks
        if task["scheduled_for"] == today and task["status"] == "open"
    ]


def ask_user(question: str) -> str:
    """Ask the CLI user a question and return their answer."""
    print(f"\nשאלה: {question}")
    return input("תשובה: ").strip()


def create_task_file(content: str, file_format: str) -> str:
    """Save task-table content in the selected format under exports/."""
    supported_formats = {"txt", "csv", "json"}
    if file_format not in supported_formats:
        raise ValueError(f"Unsupported file format: {file_format}")
    if not content.strip():
        raise ValueError("File content cannot be empty.")
    if file_format == "json":
        json.loads(content)

    today = date.today().isoformat()
    export_dir = Path(__file__).with_name("exports")
    export_dir.mkdir(exist_ok=True)
    output_path = export_dir / f"tasks_{today}.{file_format}"
    encoding = "utf-8-sig" if file_format == "csv" else "utf-8"
    output_path.write_text(content, encoding=encoding)
    return str(output_path)


read_tasks_tool = {
    "type": "function",
    "name": "read_tasks",
    "description": "קורא את tasks.json ומחזיר משימות פתוחות שתוכננו להיום.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    "strict": True,
}

ask_user_tool = {
    "type": "function",
    "name": "ask_user",
    "description": "מציג שאלה למשתמש דרך ה-CLI ומחזיר את תשובתו.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "שאלה אחת ברורה וממוקדת למשתמש.",
            }
        },
        "required": ["question"],
        "additionalProperties": False,
    },
    "strict": True,
}

create_task_file_tool = {
    "type": "function",
    "name": "create_task_file",
    "description": (
        "יוצר קובץ עם טבלת המשימות של היום בתיקיית exports. "
        "יש להפעיל רק אחרי שהמשתמש אישר ייצוא ובחר פורמט."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "תוכן הטבלה בפורמט שנבחר.",
            },
            "file_format": {
                "type": "string",
                "enum": ["txt", "csv", "json"],
                "description": "פורמט הקובץ שאישר המשתמש.",
            },
        },
        "required": ["content", "file_format"],
        "additionalProperties": False,
    },
    "strict": True,
}

tools = [read_tasks_tool, ask_user_tool, create_task_file_tool]

TOOLS_REGISTER = {
    "read_tasks": read_tasks,
    "ask_user": ask_user,
    "create_task_file": create_task_file,
}


def run_agent(client: OpenAI, history: list[Any], user_input: str) -> None:
    """Run one user turn, preserving conversation history across turns."""
    history.append({"role": "user", "content": user_input})

    for _ in range(MAX_TURNS):
        response = client.responses.create(
            model=os.environ["MODEL"],
            instructions=SYSTEM_PROMPT,
            input=history,
            temperature=0.2,
            tools=tools,
        )

        output_text = response.output_text
        if output_text:
            print(f"\nאייג׳נט: {output_text}")

        function_calls = [
            item for item in response.output if item.type == "function_call"
        ]
        history.extend(response.output)

        if not function_calls:
            return

        for call in function_calls:
            if call.name not in TOOLS_REGISTER:
                raise ValueError(f"Unknown tool requested by model: {call.name}")

            arguments = json.loads(call.arguments)
            print(f"\nכלי: {call.name}")
            result = TOOLS_REGISTER[call.name](**arguments)
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )

    print(f"\nהגענו למגבלת {MAX_TURNS} סבבי מודל לבקשה זו.")


def main() -> None:
    load_dotenv()
    required_variables = ("OPENAI_API_KEY", "MODEL", "BASE_URL")
    missing_variables = [
        name for name in required_variables if not os.getenv(name)
    ]
    if missing_variables:
        names = ", ".join(missing_variables)
        raise RuntimeError(f"Missing required environment variables: {names}")

    ssl_context = ssl.create_default_context()
    ssl_context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    http_client = httpx2.Client(verify=ssl_context)

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["BASE_URL"],
        http_client=http_client,
    )

    print("אייג׳נט לוח המשימות מוכן. לחצי Enter בשורה ריקה כדי לצאת.")
    history: list[Any] = []
    while True:
        user_input = input("\nאת: ").strip()
        if not user_input:
            break
        run_agent(client, history, user_input)


if __name__ == "__main__":
    main()