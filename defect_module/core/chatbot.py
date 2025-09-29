# import openai

# openai.api_key = "EMPTY"
# openai.api_base = "http://172.28.102.8:6668/v1"
# my_model = "Phind-CodeLlama-34B-v2"

from openai import OpenAI
import time

class ChatBot:

    def __init__(self, api_key, base_url, model, system_prompt, temperature=0, max_tokens=4096):
        self.history = []

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        # "sk-6bb712413c554d1eb8f8088be901c3c0"
        # "https://api.deepseek.com/beta"
        # "deepseek-chat"
        
        self.system_prompt = system_prompt
        self.temperature = temperature       
        self.max_tokens = max_tokens
        self.max_context = 20
        # ("You are an intelligent programming assistant to help user writing python unit tests. "
                            #   "If you provide code in your response, the code you write should be in format ```python <code> ```")

    def chat(self, prompt, prefix_output, add_to_history):
        prompts = [{"role":"system", "content": self.system_prompt}]
        
        for history in self.history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})
        
        prompts.append({"role": "user", "content": prompt})
        # prompts.append({"role": "assistant", "content": prefix_output, "prefix": True})

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        get_response = False
        while not get_response:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=prompts,
                    temperature=self.temperature
                )
                res = response.choices[0].message.content
                get_response = True
            except Exception as e:
                print(e)
                time.sleep(60)

        if len(self.history) > self.max_context:
            self.history.pop()
        if add_to_history:
            self.history.append({"question":prompt,"answer":res})
        
        return res
    
    def chat_with_additional_history(self, prompt, prefix_output, add_to_history, additional_history):
        prompts = [{"role":"system", "content": self.system_prompt}]
        
        for history in additional_history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})
        
        for history in self.history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})
        
        prompts.append({"role": "user", "content": prompt})
        # prompts.append({"role": "assistant", "content": prefix_output, "prefix": True})

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        response = client.chat.completions.create(
            model=self.model,
            messages=prompts,
            temperature=self.temperature,
            # stop=["```"],
            stream=False
        )
        
        try:
            rate_limit = response.message
            if 'limit' in rate_limit:
                time.sleep(60)
                response = client.chat.completions.create(
                    model=self.model,
                    messages=prompts,
                    temperature=self.temperature,
                    # stop=["```"],
                    stream=False
                )
        except Exception as e:
            pass
            
        res = response.choices[0].message.content
        
        if len(self.history) > self.max_context:
            self.history.pop()
        if add_to_history:
            self.history.append({"question":prompt,"answer":res})
        
        return res

    
    def clear_history(self):
        self.history = []
        
        
    def add_history(self, question, answer):
        if len(self.history) > self.max_context:
            self.history.pop()
        self.history.append({"question": question, "answer": answer})
        
    def show_history(self):
        print('=' * 20)
        print('System Prompt:')
        print(self.system_prompt)
        for history in self.history:
            print("Question:")
            print(history["question"])
            print("Answer:")
            print(history["answer"])
            print("-" * 20)
        print('=' * 20)

    def get_history(self, additional_history=[]):
        # concat history to string
        history_str = ''
        for history in additional_history:
            history_str += f"Question: {history['question']}\n"
            history_str += f"Answer: {history['answer']}\n"
        
        for history in self.history:
            history_str += f"Question: {history['question']}\n"
            history_str += f"Answer: {history['answer']}\n"
        return history_str

if __name__ == "__main__":
    api_key = 'sk-84aafc4559f745d997591b9919b5dcc2'
    base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    model = 'qwen3-coder-plus'
    generation_system_prompt = 'You are an intelligent assistant.'
    temperature = 0
    
    api_key = "sk-ef839bf32a294f0db520b4e0aec611f5"
    base_url = "https://api.deepseek.com"
    model = "deepseek-chat"
    temperature = 0
    
    chatbot = ChatBot(api_key, base_url, model, generation_system_prompt, temperature)
    
    prompt = 'hi, who are you'
    chatbot.chat(prompt, '',True)
    
    # display(chatbot.history)
    for history in chatbot.history:
        print("Question:")
        print(history["question"])
        print("Answer:")
        print(history["answer"])
    print("----")
