
from conversational_rag import rewrite_question

history = [
    {
        "role": "user",
        "content": "What is the warranty period for S-Presso?"
    },
    {
        "role": "assistant",
        "content": (
            "The standard S-Presso warranty is "
            "36 months or 100,000 km."
        )
    },
    {
        "role": "user",
        "content": "What happens if my vehicle crosses 100,000 km?"
    },
    {
        "role": "assistant",
        "content": (
            "The standard vehicle warranty is subject "
            "to its time and mileage limits."
        )
    }
]

questions = [
    "What about the lead acid battery?",
    "And what about the hybrid battery?",
    "What happens if my vehicle crosses 100,000 km?"
]

for question in questions:
    rewritten = rewrite_question(question, history)

    print("\nOriginal:", question)
    print("Rewritten:", rewritten)
    print("-" * 60)
