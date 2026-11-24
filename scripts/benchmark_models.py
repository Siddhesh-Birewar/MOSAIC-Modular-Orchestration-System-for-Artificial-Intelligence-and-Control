"""Manually compare installed MOSAIC chat models; this script is never run automatically."""

import argparse
import os
import statistics
import time

import httpx

PROMPTS = [
    ("English", "Explain what a Python function is in two short sentences."),
    ("Hindi", "पाइथन में list और tuple के बीच अंतर संक्षेप में समझाइए।"),
    ("Hinglish", "API aur database ka relation ek simple example se samjhao."),
    ("Reasoning", "A box has 3 red and 2 blue balls. What is the probability of drawing red? Explain briefly."),
    ("Coding", "Write a Python function that returns the factorial of a non-negative integer."),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=os.getenv("MOSAIC_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--model", action="append", dest="models", help="Model to measure; repeat to compare")
    args = parser.parse_args()
    models = args.models or [
        model.strip()
        for model in os.getenv("MOSAIC_ALLOWED_MODELS", "gpt-oss:20b,qwen3:8b").split(",")
        if model.strip()
    ]

    with httpx.Client(timeout=300) as client:
        installed = {item.get("name") for item in client.get(f"{args.api}/models").raise_for_status().json()["models"]}
        selected = [model for model in models if model in installed]
        if not selected:
            raise SystemExit("None of the selected models are installed and available in MOSAIC.")
        for model in selected:
            durations: list[float] = []
            rates: list[float] = []
            for category, prompt in PROMPTS:
                started = time.perf_counter()
                response = client.post(f"{args.api}/chat", json={"message": prompt, "model": model})
                response.raise_for_status()
                result = response.json()
                duration = time.perf_counter() - started
                durations.append(duration)
                tps = result["metrics"].get("generation_tokens_per_second")
                if tps is not None:
                    rates.append(tps)
                print(f"{model} | {category} | {duration:.2f}s | {tps or 'n/a'} tokens/s")
            print(
                f"{model} summary | mean {statistics.mean(durations):.2f}s | "
                f"mean generation {statistics.mean(rates):.2f} tokens/s" if rates else
                f"{model} summary | mean {statistics.mean(durations):.2f}s | generation rate n/a"
            )


if __name__ == "__main__":
    main()
