"""
Evaluate table retrieval using benchmark questions.
"""

import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from schema.schema_discovery import discover_schema
from utils.pinecone_schema_query import retrieve_top_schema


@dataclass
class RetrievalMetrics:
    ground_truth_tables: set[str]
    retrieved_tables: set[str]
    matched_tables: set[str]
    extra_tables: set[str]
    missing_tables: set[str]
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1_score: float


class RetrievalEvaluator:
    @staticmethod
    def evaluate(ground_truth: list[str], retrieved: list[str]) -> RetrievalMetrics:
        ground_truth_tables = set(ground_truth)
        retrieved_tables = set(retrieved)

        matched_tables = ground_truth_tables & retrieved_tables
        extra_tables = retrieved_tables - ground_truth_tables
        missing_tables = ground_truth_tables - retrieved_tables

        true_positive = len(matched_tables)
        false_positive = len(extra_tables)
        false_negative = len(missing_tables)

        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1_score = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        return RetrievalMetrics(
            ground_truth_tables=ground_truth_tables,
            retrieved_tables=retrieved_tables,
            matched_tables=matched_tables,
            extra_tables=extra_tables,
            missing_tables=missing_tables,
            true_positive=true_positive,
            false_positive=false_positive,
            false_negative=false_negative,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
        )


class BenchmarkEvaluator:
    def __init__(
        self,
        connection_string: str | None = None,
        benchmark_path: Path | None = None,
        semantic_top_k: int = 5,
        final_top_k: int = 3,
        max_depth: int = 2,
    ):
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise SystemExit("Set DATABASE_URL in .env before running evaluator.py")

        self.pinecone_namespace = self.connection_string.split("/")[-1].split("?")[0]

        self.semantic_top_k = semantic_top_k
        self.final_top_k = final_top_k
        self.max_depth = max_depth

        self.schema = discover_schema(self.connection_string)
        self.relationship_graph = self._build_relationship_graph()

        self.benchmark_path = benchmark_path or Path(__file__).parent / "benchmark.json"
        if not self.benchmark_path.exists():
            raise SystemExit(f"Benchmark file not found: {self.benchmark_path}")

        with open(self.benchmark_path, "r", encoding="utf-8") as file:
            self.benchmark = json.load(file)

        self.results = []

    def _build_relationship_graph(self) -> dict[str, set[str]]:
        graph = {table_name: set() for table_name in self.schema}

        for table_name, table in self.schema.items():
            for fk in table.foreign_keys:
                if fk.ref_table in graph:
                    graph[table_name].add(fk.ref_table)
                    graph[fk.ref_table].add(table_name)

        return graph

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))

    def _rank_tables(self, question: str) -> list[tuple[str, float]]:
        question_tokens = self._tokens(question)
        ranked = []

        for table_name, table in self.schema.items():
            table_tokens = self._tokens(table_name.replace("_", " "))
            score = 0.0

            if table_name.lower() in question.lower():
                score += 5.0

            score += 2.0 * len(question_tokens & table_tokens)

            for column in table.columns:
                column_name = column.name.lower()
                column_tokens = self._tokens(column.name.replace("_", " "))

                if column_name in question.lower():
                    score += 3.0

                score += 1.0 * len(question_tokens & column_tokens)

            if score > 0:
                ranked.append((table_name, score))

        return sorted(ranked, key=lambda item: item[1], reverse=True)

    def _semantic_candidates(self, question: str) -> list[dict]:
        try:
            matches = retrieve_top_schema(
                question=question, 
                top_k=self.semantic_top_k, 
                namespace=self.pinecone_namespace
            )
        except Exception as exc:
            print(f"\n[Warning] Semantic search failed: {exc}")
            return []

        candidates = []
        for _, score, metadata in matches:
            table_name = metadata.get("table") or metadata.get("table_name")
            if table_name in self.schema:
                candidates.append(
                    {
                        "table": table_name,
                        "score": float(score),
                        "source": "semantic",
                    }
                )

        return candidates

    def _merge_candidates(
        self,
        keyword_candidates: list[dict],
        semantic_candidates: list[dict],
    ) -> list[dict]:
        merged: dict[str, dict] = {}

        max_keyword_score = max(
            (candidate["score"] for candidate in keyword_candidates),
            default=1.0,
        )

        for candidate in keyword_candidates:
            table_name = candidate["table"]
            normalized_score = candidate["score"] / max_keyword_score
            merged[table_name] = {
                "table": table_name,
                "score": normalized_score,
                "source": "keyword",
            }

        for candidate in semantic_candidates:
            table_name = candidate["table"]
            existing = merged.get(table_name)
            if existing:
                existing["score"] += candidate["score"]
                existing["source"] = "keyword+semantic"
            else:
                merged[table_name] = candidate

        return sorted(
            merged.values(),
            key=lambda candidate: candidate["score"],
            reverse=True,
        )[: self.final_top_k]

    def _expand_relationships(self, selected_tables: list[str]) -> set[str]:
        expanded = set(selected_tables)
        frontier = set(selected_tables)

        for _ in range(self.max_depth):
            next_frontier = set()

            for table_name in frontier:
                next_frontier.update(self.relationship_graph.get(table_name, set()))

            next_frontier -= expanded
            if not next_frontier:
                break

            expanded.update(next_frontier)
            frontier = next_frontier

        return expanded

    def evaluate(self):
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0

        print("=" * 100)
        print("TABLE RETRIEVER BENCHMARK")
        print("=" * 100)

        for sample in self.benchmark:
            question = sample["question"]
            difficulty = sample.get("difficulty", "unknown")
            ground_truth = sample["ground_truth"]

            ranked_tables = self._rank_tables(question)
            keyword_candidates = [
                {"table": table, "score": float(score), "source": "keyword"}
                for table, score in ranked_tables
            ]

            semantic_candidates = self._semantic_candidates(question)

            merged_candidates = self._merge_candidates(
                keyword_candidates=keyword_candidates,
                semantic_candidates=semantic_candidates,
            )
            seed_tables = [candidate["table"] for candidate in merged_candidates]

            retrieved_tables = list(self._expand_relationships(seed_tables))

            metrics = RetrievalEvaluator.evaluate(
                ground_truth=ground_truth,
                retrieved=retrieved_tables,
            )

            total_precision += metrics.precision
            total_recall += metrics.recall
            total_f1 += metrics.f1_score

            self.results.append(
                {
                    "Difficulty": difficulty,
                    "Question": question,
                    "Ground Truth": ", ".join(sorted(metrics.ground_truth_tables)),
                    "Retrieved": ", ".join(sorted(metrics.retrieved_tables)),
                    "Matched": ", ".join(sorted(metrics.matched_tables)),
                    "Extra": ", ".join(sorted(metrics.extra_tables)),
                    "Missing": ", ".join(sorted(metrics.missing_tables)),
                    "TP": metrics.true_positive,
                    "FP": metrics.false_positive,
                    "FN": metrics.false_negative,
                    "Precision": round(metrics.precision, 4),
                    "Recall": round(metrics.recall, 4),
                    "F1": round(metrics.f1_score, 4),
                }
            )

            print("\n" + "-" * 100)
            print(f"Question      : {question}")
            print(f"Difficulty    : {difficulty}")
            print()
            print(f"Ground Truth  : {metrics.ground_truth_tables}")
            print(f"Retrieved     : {metrics.retrieved_tables}")
            print()
            print(f"Matched       : {metrics.matched_tables}")
            print(f"Extra         : {metrics.extra_tables}")
            print(f"Missing       : {metrics.missing_tables}")
            print()
            print(f"Precision     : {metrics.precision:.2%}")
            print(f"Recall        : {metrics.recall:.2%}")
            print(f"F1 Score      : {metrics.f1_score:.2%}")

        total_questions = len(self.benchmark)
        avg_precision = total_precision / total_questions if total_questions else 0.0
        avg_recall = total_recall / total_questions if total_questions else 0.0
        avg_f1 = total_f1 / total_questions if total_questions else 0.0

        print("\n")
        print("=" * 100)
        print("FINAL BENCHMARK RESULTS")
        print("=" * 100)
        print(f"Total Questions     : {total_questions}")
        print(f"Average Precision   : {avg_precision:.2%}")
        print(f"Average Recall      : {avg_recall:.2%}")
        print(f"Average F1 Score    : {avg_f1:.2%}")

        self.save_csv()

    def save_csv(self):
        if not self.results:
            print("\nNo results to save.")
            return

        csv_path = Path(__file__).parent / "retrieval_report.csv"

        with open(csv_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.results[0].keys())
            writer.writeheader()
            writer.writerows(self.results)

        print("\n")
        print(f"CSV Report Saved -> {csv_path}")


if __name__ == "__main__":
    evaluator = BenchmarkEvaluator()
    evaluator.evaluate()
