import openai


API_KEY = "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"
client = openai.OpenAI(api_key=API_KEY)


response = client.responses.create(
    model="gpt-4.1-mini",
    input="Hello, world!",
)

print(response.output_text)