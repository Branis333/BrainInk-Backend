import google.generativeai as genai
genai.configure(api_key="AIzaSyCBfVN4MtmoAAIsyiaBvJYhds_0XnbTjiA")

for model in genai.list_models():
    print(model)