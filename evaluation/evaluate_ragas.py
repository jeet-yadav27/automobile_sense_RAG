
import asyncio
import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ragas.llms import llm_factory
from ragas.embeddings import embedding_factory
from ragas.metrics.collections import (
    Faithfulness,
    AnswerRelevancy,
)

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

INPUT_CSV = ROOT / "evaluation" / "reports" / "live_retrieval_results.csv"
OUTPUT_CSV = ROOT / "evaluation" / "reports" / "ragas_scores.csv"


async def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing")

    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    client = AsyncOpenAI()

    evaluator_llm = llm_factory(
        model=os.getenv("RAGAS_MODEL", "gpt-4o-mini"),
        client=client,
    )

    evaluator_embeddings = embedding_factory(
        provider="openai",
        model="text-embedding-3-small",
        client=client,
    )

    faithfulness = Faithfulness(llm=evaluator_llm)

    answer_relevancy = AnswerRelevancy(
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
    )

    df = pd.read_csv(INPUT_CSV)
    results = []

    try:
        for index, row in df.iterrows():
            question = str(row["question"])
            answer = str(row["answer"])

            try:
                contexts = json.loads(row["retrieved_contexts"])
                if not isinstance(contexts, list):
                    raise ValueError("Contexts must be a list")
                contexts = [str(c) for c in contexts]
            except (TypeError, ValueError) as exc:
                print(f"Invalid contexts in row {index}: {exc}")
                contexts = []

            print(
                f"\nEvaluating {index + 1}/{len(df)}: "
                f"{row['method']}",
                flush=True,
            )

            faith_score = None
            relevancy_score = None

            if contexts:
                try:
                    faith_result = await faithfulness.ascore(
                        user_input=question,
                        response=answer,
                        retrieved_contexts=contexts,
                    )
                    faith_score = faith_result.value
                except Exception as exc:
                    print(f"Faithfulness failed: {exc}")

            try:
                relevancy_result = await answer_relevancy.ascore(
                    user_input=question,
                    response=answer,
                )
                relevancy_score = relevancy_result.value
            except Exception as exc:
                print(f"Answer relevancy failed: {exc}")

            results.append({
                **row.to_dict(),
                "faithfulness": faith_score,
                "answer_relevancy": relevancy_score,
            })

            print("Faithfulness:", faith_score)
            print("Answer relevancy:", relevancy_score)

        result_df = pd.DataFrame(results)

        OUTPUT_CSV.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result_df.to_csv(
            OUTPUT_CSV,
            index=False,
            encoding="utf-8-sig",
        )

        print("\nAverage scores by method:")
        print(
            result_df.groupby("method")[
                ["faithfulness", "answer_relevancy"]
            ].mean().round(3)
        )

        print("\nSaved:", OUTPUT_CSV)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
