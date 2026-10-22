
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

# 1. Load configuration from the local .env file
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not api_key or api_key == "your_actual_api_key_here":
    raise RuntimeError(
        "Set your real OPENAI_API_KEY in the local .env file."
    )

# 2. Create the API client
client = OpenAI(api_key=api_key)

# 3. Illustrative passage, not official warranty wording
passage = """
Illustrative example only:
If an engine overheats, the driver should stop the vehicle
in a safe place and contact an authorized service center.
This example policy covers overheating caused by a manufacturing defect.” 
Ask whether overheating caused by a manufacturing defect is covered.

"""

question = "Is engine overheating covered under warranty?"

# 4. Define the model's behavior
system_prompt = """
You are a warranty-document assistant.

Use only the passage supplied by the user.
Never invent warranty coverage, exclusions, or procedures.
If the passage does not contain enough information to answer,
set refused to true and say that the manual passage is insufficient.

Return valid JSON with these fields:
{
  "answer": "string",
  "refused": true,
  "citations": []
}

Citations must only refer to source details explicitly provided.


Do not invent page numbers or sections.
"""

# 5. Call the model using JSON output mode
response = client.chat.completions.create(
    model=model,
    temperature=0,
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Passage:\n{passage}\n\n"
                f"Question: {question}"
            ),
        },
    ],
)

# 6. Extract and validate the response
message = response.choices[0].message

if not message.content:
    raise RuntimeError("The model returned an empty response.")

result = json.loads(message.content)

print("\n--- MODEL ---")
print(response.model)

print("\n--- ANSWER ---")
print(json.dumps(result, indent=2))

print("\n--- TOKEN USAGE ---")
print("Prompt tokens:", response.usage.prompt_tokens)
print("Completion tokens:", response.usage.completion_tokens)
print("Total tokens:", response.usage.total_tokens)
