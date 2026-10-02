from ollama import chat

response = chat(
    model="gemma3:4b",
    messages=[
        {
            "role": "user",
            "content": "Give me one simple software engineering interview question."
        }
    ]
)

print(response.message.content)