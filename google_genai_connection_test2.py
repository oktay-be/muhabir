import google.generativeai as genai

genai.configure(api_key="AIzaSyAQ9ZzKNMi6Z83wWWbx0-e-DQDM3awN7Hw")

model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
resp = model.generate_content("Summarize these articles…")
print(resp.text)
