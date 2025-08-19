from openai import OpenAI
from dotenv import load_dotenv
import os
from typing import Iterable

# Load environment variables (expects OPENAI_API_KEY)
load_dotenv()
client = OpenAI()


def generate_response( prompt: str | None):

    result = client.responses.create(
        model="gpt-5",
        input=prompt,
        reasoning={ "effort": "low" },
        text={ "verbosity": "low" },
    )

    return result.output_text



def generate_response_with_search ( prompt: str | None):

    response = client.responses.create(
        model="gpt-5",
        tools=[{"type": "web_search_preview"}],
        input= prompt
    )
    return response.output_text


def generate_response_40(prompt: str | None):
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2048,
        top_p=1
    )
    return response.choices[0].message.content


