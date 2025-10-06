import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

# .env 파일에서 환경 변수 로드
load_dotenv()


def get_llm():
    return AzureChatOpenAI(
        openai_api_key=os.getenv("AOAI_API_KEY"),
        azure_endpoint=os.getenv("AOAI_ENDPOINT"),
        azure_deployment=os.getenv("AOAI_DEPLOY_GPT4O"),
        api_version=os.getenv("AOAI_API_VERSION"),
        # temperature=0.7,
    )
