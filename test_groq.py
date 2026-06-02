"""Quick check: Groq API responds."""
from langchain_groq import ChatGroq
from backend.config import settings


def test_groq():
    llm = ChatGroq(api_key=settings.groq_api_key, model="llama-3.3-70b-versatile")
    response = llm.invoke("Di solo 'OK' y nada más.")
    print(f"Groq response: {response.content}")


if __name__ == "__main__":
    test_groq()
