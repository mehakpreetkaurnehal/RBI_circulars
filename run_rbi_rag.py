from rbi_retriever import retrieve_chunks
from rbi_reranker import rerank_chunks
from rbi_generate_answer import generate_answer
from rbi_evaluate_answer import evaluate_answer

if __name__ == "__main__":
    query = "What guidelines has RBI issued for digital payment security?"

    # 1. Retrieve
    retrieved = retrieve_chunks(query)

    # 2. Rerank
    final_chunks = rerank_chunks(retrieved, top_k=8)

    # 3. Generate answer
    answer = generate_answer(query, final_chunks)

    # 4. Evaluate answer
    evaluation = evaluate_answer(query, answer)

    print("\n================ ANSWER ================\n")
    print(answer)

    print("\n=========== CHUNK SCORES ===============\n")
    for c in final_chunks:
        print(f"{c['semantic_score']:.3f} | {c['title']}")

    print("\n=========== EVALUATION =================\n")
    print(evaluation)
