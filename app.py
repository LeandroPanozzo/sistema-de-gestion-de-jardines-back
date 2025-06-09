from openai import OpenAI
from openai.types import OpenAIError

client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

try:
    chat = client.chat.completions.create(
        model="deepseek/deepseek-r1:free",
        messages=[
            {"role": "user", "content": "estamos en un jardin maternal, asi que debes responder como si te estuvieran consultando cosas propias de un jardin maternal, responde siempre en español"}
        ]
    )
    print(chat.choices[0].message.content)

except OpenAIError as e:
    print(f"Error: {e}")
