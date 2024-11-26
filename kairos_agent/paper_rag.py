from openai import OpenAI
from pinecone import Pinecone
from typing import List, Dict


def process_query(client, index, query: str, top_k: int = 10, min_score: float = 0.001) -> str:
    """
    주어진 쿼리에 대해 전체 작업 흐름을 실행합니다.

    Args:
        client (OpenAI): OpenAI 클라이언트.
        index (Index): Pinecone 인덱스 객체.
        query (str): 사용자 쿼리.
        top_k (int): 검색할 상위 문서 수. 기본값은 10.
        min_score (float): 문서 필터링을 위한 최소 점수. 기본값은 0.001.

    Returns:
        str: GPT의 응답 결과.
    """
    try:
        # 1. 문서 검색
        response = client.embeddings.create(input=query, model="text-embedding-ada-002")
        query_embeddings = response.data[0].embedding

        search_results = index.query(
            namespace="",
            vector=query_embeddings,
            top_k=top_k,
            include_metadata=True,
        )

        # 2. 관련 문서 필터링
        relevant_documents = [
            match for match in search_results["matches"] if match["score"] >= min_score
        ]

        if not relevant_documents:
            return "No relevant documents found."

        # 3. 문서 재정렬
        sorted_docs = sorted(relevant_documents, key=lambda x: x["score"], reverse=True)

        # 4. 컨텍스트 생성
        contexts = ""
        for doc in sorted_docs:
            contexts += doc["metadata"]["_node_content"] + "\n\n"
        context_prompt = f"[Context]\n{contexts}"

        # 5. GPT 호출
        messages = [
            {"role": "system", "content": "You are a highly knowledgeable and specialized assistant designed to assist with academic research using Retrieval-Augmented Generation (RAG) techniques. Your primary role is to analyze and synthesize relevant academic papers by leveraging provided context and retrieved data. Focus on producing accurate, concise, and insightful summaries of the retrieved documents, prioritizing high-quality information. Ensure your responses are based on factual and evidence-backed content, while maintaining clarity and relevance to the query. Use technical terminology appropriately for academic purposes and reference the most relevant parts of the context to address the query in detail."},
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": query},
        ]
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
            max_tokens=1024,
        )

        return gpt_response.choices[0].message.content

    except Exception as e:
        return f"An error occurred: {e}"