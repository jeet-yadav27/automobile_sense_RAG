
from openai import OpenAI

client = OpenAI()


def rewrite_query(question: str) -> str:
    prompt = f"""
You rewrite user questions for searching an
S-Presso vehicle owner's manual.

Rules:
- Preserve the user's original meaning.
- Expand abbreviations when helpful.
- Identify the intended subject.
- Do not invent vehicle details.
- Return only the rewritten search question.

Question: {question}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()
