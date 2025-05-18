import os
from openai import AsyncOpenAI
import asyncio

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_gpt(prompt):
    try:
        response = asyncio.run(
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"GPT 응답 실패: {str(e)}"
