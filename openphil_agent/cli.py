"""
Command-line interface for the AI Scientist.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .ai_scientist import AIScientist
from .coding_agent import get_agent_model


def print_model_configuration():
    """Print the current model configuration for all agents and Aider."""
    print("\n" + "="*60)
    print("MODEL CONFIGURATION")
    print("="*60)
    
    aider_model = os.environ.get("AIDER_MODEL", "openrouter/openai/gpt-4o-mini")
    aider_temp = os.environ.get("AIDER_TEMPERATURE", "0.5")
    print(f"Aider Model: {aider_model} (temperature: {aider_temp})")
    
    print(f"Planning Agent: {get_agent_model('planning')}")
    print(f"Decision Agent: {get_agent_model('decision')}")
    print(f"LLM Agent: {get_agent_model('llm')}")
    print(f"HumanEval Agent: {get_agent_model('humaneval')}")
    print(f"FileMapper Agent: {get_agent_model('filemapper')}")
    
    has_api_key = "OPENROUTER_API_KEY" in os.environ
    print(f"OPENROUTER_API_KEY present: {has_api_key}")
    print("="*60 + "\n")


def sanitize_json_with_comments(text: str) -> str:
    """
    Sanitize JSON text that may contain comments and trailing commas.
    Removes // comments (but not in URLs), /* */ comments, and trailing commas before } or ].
    """
    lines = text.split('\n')
    sanitized_lines = []
    
    for line in lines:
        if line.strip().startswith('//'):
            continue
        in_string = False
        result = []
        i = 0
        while i < len(line):
            if line[i] == '"' and (i == 0 or line[i-1] != '\\'):
                in_string = not in_string
                result.append(line[i])
            elif not in_string and i < len(line) - 1 and line[i:i+2] == '//':
                break
            else:
                result.append(line[i])
            i += 1
        sanitized_lines.append(''.join(result))
    
    sanitized = '\n'.join(sanitized_lines)
    sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
    sanitized = re.sub(r',(\s*[}\]])', r'\1', sanitized)
    
    return sanitized


def main():
    parser = argparse.ArgumentParser(
        description="AI Scientist - Autonomous research figure recreation"
    )
    parser.add_argument(
        "--task-dir",
        type=str,
        required=True,
        help="Path to the task directory containing prompt.md and paper_markdown.md",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="run_output",
        help="Base output directory (default: run_output)",
    )
    parser.add_argument(
        "--aider-model",
        type=str,
        default=None,
        help="Model to use for Aider coding assistant (default: from AIDER_MODEL env var or openrouter/openai/gpt-4o-mini)",
    )
    parser.add_argument(
        "--evaluator-model",
        type=str,
        default="openai/gpt-4o",
        help="Model to use for figure evaluation (default: openai/gpt-4o)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=200,
        help="Maximum number of ReAct loop iterations (default: 200)",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=90,
        help="Time limit in minutes (default: 90)",
    )
    parser.add_argument(
        "--eval-threshold",
        type=float,
        default=0.9,
        help="Evaluation score threshold for submission (default: 0.9)",
    )
    
    args = parser.parse_args()
    
    task_dir = Path(args.task_dir)
    if not task_dir.exists():
        print(f"Error: Task directory not found: {task_dir}")
        sys.exit(1)
    
    prompt_file = task_dir / "prompt.md"
    paper_file = task_dir / "paper_markdown.md"
    extra_links_file = task_dir / "extra_links.json"
    
    if not prompt_file.exists():
        print(f"Error: prompt.md not found in {task_dir}")
        sys.exit(1)
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()
    
    paper_text = ""
    if paper_file.exists():
        with open(paper_file, "r", encoding="utf-8") as f:
            paper_text = f.read()
    
    extra_links = None
    if extra_links_file.exists():
        try:
            with open(extra_links_file, "r", encoding="utf-8") as f:
                text = f.read()
            sanitized = sanitize_json_with_comments(text)
            extra_links = json.loads(sanitized)
            
            if "docs_link" in extra_links and isinstance(extra_links["docs_link"], list):
                extra_links["docs_link"] = [
                    link.replace("docs_link = ", "").strip() 
                    for link in extra_links["docs_link"]
                ]
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse {extra_links_file}: {e}")
            print("Continuing without extra_links...")
            extra_links = None
    
    task_name = task_dir.name
    
    print(f"Starting AI Scientist on task: {task_name}")
    print(f"Prompt: {prompt[:100]}...")
    print(f"Paper length: {len(paper_text)} characters")
    print(f"Output directory: {args.output_dir}")
    
    print_model_configuration()
    
    scientist = AIScientist(
        aider_model=args.aider_model,
        evaluator_model=args.evaluator_model,
        max_steps=args.max_steps,
        time_limit_minutes=args.time_limit,
        eval_threshold=args.eval_threshold,
    )
    
    success, figure_path, logs, evaluation = scientist.run(
        paper_text=paper_text,
        prompt=prompt,
        task_name=task_name,
        output_dir=Path(args.output_dir),
        extra_links=extra_links,
        task_dir=task_dir,
    )
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"Success: {success}")
    if figure_path:
        print(f"Figure: {figure_path}")
    if evaluation:
        print(f"Evaluation score: {evaluation.get('score', 'N/A')}")
        print(f"Should submit: {evaluation.get('should_submit', 'N/A')}")
    print("="*60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
