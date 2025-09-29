from loguru import logger
from openai import OpenAI

class ChatBot:
    def __init__(
        self,
        api_base: str,
        model: str = "Qwen/Qwen3-Next-80B-A3B-Instruct",
        api_key: str = "EMPTY",         
        temperature: float = 0,
        max_tokens: int = 4096
    ):
        self.history = []
        self.model = model
        self.max_context = 10
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = (
            "You are an intelligent programming assistant to help user writing Java unit tests use Junit5."
            "If you provide code in your response, the code you write should be in format ```java <code> ```"
        )
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=api_base
            )
            logger.info(f"OpenAI client initialized with base_url={api_base}, model={model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    def chat(self, prompt, add_to_history):
        logger.info("Chat API call started")
        prompts = [{"role": "system", "content": self.system_prompt}]

        for history in self.history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})

        prompts.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=prompts,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            res = response.choices[0].message.content
            logger.info("Chat API call finished")
        except Exception as e:
            logger.error(f"Error during chat completion: {e}")
            raise

        if len(self.history) >= self.max_context:
            self.history.pop(0)  # 保留最新对话，移除最旧的

        if add_to_history:
            self.history.append({"question": prompt, "answer": res})

        return res

    def chat_cache(self, stage1_prompt, stage1_response=None, stage2_prompt=None):
        logger.info("Chat cache API call started")
        prompts = [{"role": "system", "content": self.system_prompt}]
        prompts.append({"role": "user", "content": stage1_prompt})
        if stage1_response:
            prompts.append({"role": "assistant", "content": stage1_response})
        if stage2_prompt:
            prompts.append({"role": "user", "content": stage2_prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=prompts,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            res = response.choices[0].message.content
            logger.info("Chat cache API call finished")
        except Exception as e:
            logger.error(f"Error during chat_cache completion: {e}")
            raise
        return res


# ===== 示例用法 =====
if __name__ == "__main__":
    # 示例 1：调用本地 FastChat / vLLM（无需真实 key）
    chatbot_local = ChatBot(
        api_base="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen3-Next-80B-A3B-Instruct",
        api_key=""
    )

    # 示例 2：调用 SiliconFlow（需要真实 key，从 https://cloud.siliconflow.cn/account/ak 获取）
    # chatbot_cloud = ChatBot(
    #     api_base="https://api.siliconflow.cn/v1",
    #     model="Qwen/Qwen2.5-Coder-32B-Instruct",
    #     api_key="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # 替换为你的实际 key
    # )

    prompt = 'hi'
    response = chatbot_local.chat_cache(prompt, "")
    print(response)
    for h in chatbot_local.history:
        print("Question:", h["question"])
        print("Answer:", h["answer"])
    print("----")