import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[

        {"role": "system", "content": "You are a helpful coding assistant."},
        
       
        {"role": "user", "content": "Explain what a Python decorator is, like I'm 5."}
    ],
    
    temperature=0.7,
    
    max_tokens=500
)

print(response.choices[0].message.content)
