from ollama import chat


MODEL = "gemma3:4b"


def ask_gemma(system_prompt: str, user_prompt: str) -> str:
    response = chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    return response.message.content