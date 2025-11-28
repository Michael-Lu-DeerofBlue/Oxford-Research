"""
Main AIScientist class that orchestrates the entire research workflow.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from .coding_agent import DecisionAgent, FileMapperAgent, PlanningAgent
from .local_execution_environment import LocalExecutionEnvironment
from .self_evaluator import SelfEvaluator


class AIScientist:
    """
    Main AI Scientist that can autonomously recreate figures from papers.
    
    Workflow:
    1. Initialize work directory
    2. Plan: Generate initial plan from paper + prompt
    3. ReAct Loop: Decision → Act → Summarize → Evaluate → Stop check
    4. Submit: Package artifacts and return results
    """

    def __init__(
        self,
        aider_model: str = None,
        evaluator_model: str = "openai/gpt-4o",
        max_steps: int = 1000,
        time_limit_minutes: int = 90,
        eval_threshold: float = 0.9,
        plateau_iterations: int = 15,
    ):
        if aider_model is None:
            aider_model = os.environ.get("AIDER_MODEL", "openrouter/openai/gpt-4o-mini")
        self.aider_model = aider_model
        self.evaluator_model = evaluator_model
        self.max_steps = max_steps
        self.time_limit_seconds = time_limit_minutes * 60
        self.eval_threshold = eval_threshold
        self.plateau_iterations = plateau_iterations

    def run(
        self,
        paper_text: str,
        prompt: str,
        task_name: str,
        output_dir: Optional[Path] = None,
        extra_links: Optional[Dict] = None,
        task_dir: Optional[Path] = None,
    ) -> Tuple[bool, Optional[Path], str, Dict]:
        """
        Run the AI Scientist on a task.
        
        Args:
            paper_text: The paper content in markdown format
            prompt: The task prompt (e.g., "recreate figure 3")
            task_name: Name of the task for organizing outputs
            output_dir: Base output directory (default: run_output/)
            extra_links: Optional dict of allowed URLs for data fetching
            task_dir: Optional path to task directory (for requirements.txt)
            
        Returns:
            (success, figure_path, logs, evaluation_details)
        """
        if output_dir is None:
            output_dir = Path("run_output")
        task_output_dir = output_dir / task_name
        task_output_dir.mkdir(parents=True, exist_ok=True)

        # Create a per-run subdirectory so each AIScientist run has an isolated
        # workspace, e.g. run_output/task_eng_surfaces_waves/<run_id>/work
        run_id = time.strftime("%Y%m%d-%H%M%S")
        run_output_dir = task_output_dir / run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)

        work_dir = run_output_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        
        task_requirements_file = None
        if task_dir:
            req_file = Path(task_dir) / "requirements.txt"
            if req_file.exists():
                task_requirements_file = req_file

            # Copy common data subdirectories (e.g., Surfaces, data, images)
            # from the task directory into this run's isolated work directory,
            # so generated code can access them via relative paths.
            for subdir_name in ["Surfaces", "data", "images"]:
                src = Path(task_dir) / subdir_name
                if src.exists() and src.is_dir():
                    dst = work_dir / subdir_name
                    try:
                        import shutil
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    except TypeError:
                        # For older Python versions without dirs_exist_ok, fall back
                        # to manual merge semantics.
                        import shutil
                        if not dst.exists():
                            shutil.copytree(src, dst)
                        else:
                            for item in src.iterdir():
                                target = dst / item.name
                                if item.is_dir():
                                    if not target.exists():
                                        shutil.copytree(item, target)
                                else:
                                    shutil.copy2(item, target)
        
        env = LocalExecutionEnvironment(
            prompt=prompt,
            paper=paper_text,
            work_dir=work_dir,
            aider_model=self.aider_model,
            task_requirements_file=task_requirements_file,
        )
        
        evaluator = SelfEvaluator(
            model=self.evaluator_model,
            threshold=self.eval_threshold,
            require_consensus=True,
        )
        
        planning_agent = PlanningAgent(prompt, env)
        decision_agent = DecisionAgent(env)
        file_mapper_agent = FileMapperAgent()
        
        start_time = time.time()
        
        env.reset()
        
        print(f"\n{'='*60}")
        print(f"AI Scientist starting task: {task_name}")
        print(f"Prompt: {prompt}")
        print(f"{'='*60}\n")
        
        print("Step 1: Planning...")
        plan = planning_agent._plan_on_prompt("", use_paper=True)
        print(f"Plan generated: {plan[:200]}...")
        
        print("\nStep 2: ReAct Loop...")
        
        iteration = 0
        no_change_count = 0
        last_file_state = None
        best_evaluation = None
        evaluator_feedback = ""
        last_action = None
        repeated_action_count = 0
        
        while iteration < self.max_steps:
            iteration += 1
            elapsed_time = time.time() - start_time
            
            print(f"\n--- Iteration {iteration}/{self.max_steps} ---")
            print(f"Elapsed time: {elapsed_time:.1f}s / {self.time_limit_seconds}s")
            
            if elapsed_time > self.time_limit_seconds:
                print("⏰ Time limit reached")
                break
            
            if evaluator_feedback:
                env.logs.append(f"   Evaluator feedback: {evaluator_feedback}\n")
            
            try:
                decision_json = decision_agent._make_decision()
                decision_dict = json.loads(decision_json)
                action = decision_dict.get("action")
                argument = decision_dict.get("argument")
                use_log = decision_dict.get("use_log", False)
                
                print(f"Decision: {action}({argument[:100] if len(argument) > 100 else argument}...), use_log={use_log}")
                
                current_action_sig = f"{action}:{argument[:50]}"
                if current_action_sig == last_action:
                    repeated_action_count += 1
                    if repeated_action_count >= 3:
                        print("⚠️ Same action repeated 3+ times - likely stuck in a loop")
                        env.logs.append(f"   [System] Detected repeated action loop. The same action has been tried {repeated_action_count} times without progress. Consider: 1) Simplifying the code, 2) Checking if dependencies work on this platform, 3) Using a different approach.\n")
                        if repeated_action_count >= 5:
                            print("🛑 Breaking loop - same action repeated 5+ times")
                            break
                else:
                    repeated_action_count = 0
                last_action = current_action_sig
                
            except Exception as e:
                print(f"❌ Decision parsing error: {e}")
                continue
            
            if action not in env.available_actions():
                print(f"❌ Invalid action: {action}")
                continue
            
            if action == "submit_answer":
                print("📤 Submitting answer...")
                result = env.step(action, file_path=argument)
                print(result)
                break
            
            try:
                if action == "instruct_aider":
                    if use_log:
                        argument = f"{argument}\n\nContext from logs:\n" + "\n".join(env.get_logs()[-10:])
                    result = env.step(action, prompt=argument)
                    print(f"✓ Aider instruction completed")
                    
                    print("📋 Mapping files...")
                    file_mapping = file_mapper_agent._run_on_task(env)
                    print(f"Files mapped: {len(json.loads(file_mapping)) if file_mapping else 0} files")
                    
                elif action == "run_bash_command":
                    result = env.step(action, command=argument)
                    print(f"✓ Bash command completed: {result.get('returncode', 'N/A')}")
                    
                    if env.has_repeated_error(threshold=2):
                        print("⚠️ Same error repeated multiple times - trying alternate approach")
                        env.logs.append(f"   [System] Detected repeated error. Consider: checking dependencies, using different command syntax, or simplifying the code.\n")
                    
                else:
                    result = env.step(action, **{list(env.available_actions()[action].json_schema['properties'].keys())[0]: argument})
                    print(f"✓ Action {action} completed")
                    
            except Exception as e:
                print(f"❌ Action execution error: {e}")
                env.logs.append(f"   Action error: {str(e)}\n")
                continue
            
            current_file_state = self._get_file_state(work_dir)
            if current_file_state == last_file_state:
                no_change_count += 1
                print(f"⚠️ No file changes detected ({no_change_count}/{self.plateau_iterations})")
            else:
                no_change_count = 0
            last_file_state = current_file_state
            
            if no_change_count >= self.plateau_iterations:
                print("🛑 Plateau detected - no changes for multiple iterations")
                break
            
            png_files = list(work_dir.glob("*.png"))
            if png_files:
                print(f"🖼️ Found {len(png_files)} PNG file(s), evaluating...")
                figure_path = png_files[0]  # Use first PNG
                
                try:
                    should_submit, score, reasoning, details = evaluator.evaluate_figure(
                        figure_path=figure_path,
                        prompt=prompt,
                        paper=paper_text,
                    )
                    
                    print(f"Evaluation score: {score:.2f}")
                    print(f"Should submit: {should_submit}")
                    
                    best_evaluation = {
                        "should_submit": should_submit,
                        "score": score,
                        "reasoning": reasoning,
                        "details": details,
                    }
                    
                    evaluator_feedback = evaluator.get_feedback_for_improvement(details)
                    print(f"Feedback: {evaluator_feedback[:100]}...")
                    
                    if should_submit:
                        print("✅ Evaluator approved! Submitting...")
                        env.step("submit_answer", file_path=figure_path.name)
                        break
                        
                except Exception as e:
                    print(f"❌ Evaluation error: {e}")
                    evaluator_feedback = ""
        
        env.cleanup()
        
        logs_file = run_output_dir / "logs.jsonl"
        with open(logs_file, "w") as f:
            for log_entry in env.get_logs():
                f.write(json.dumps({"log": log_entry}) + "\n")
        
        if best_evaluation:
            eval_file = run_output_dir / "evaluation.json"
            with open(eval_file, "w") as f:
                json.dump(best_evaluation, f, indent=2)
        
        success = env.done and env.answer_file is not None
        figure_path = Path(env.answer_file) if env.answer_file else None
        
        if figure_path and figure_path.exists():
            output_figure = run_output_dir / "figure.png"
            import shutil
            shutil.copy(figure_path, output_figure)
            figure_path = output_figure
        
        print(f"\n{'='*60}")
        print(f"Task completed: {'✅ SUCCESS' if success else '❌ INCOMPLETE'}")
        print(f"Total iterations: {iteration}")
        print(f"Total time: {time.time() - start_time:.1f}s")
        if figure_path:
            print(f"Figure saved to: {figure_path}")
        print(f"{'='*60}\n")
        
        logs_summary = "\n".join(env.get_logs())
        
        return success, figure_path, logs_summary, best_evaluation or {}

    def _get_file_state(self, work_dir: Path) -> str:
        """Get a hash of the current file state for plateau detection."""
        import hashlib
        
        file_hashes = []
        for file_path in sorted(work_dir.glob("*")):
            if file_path.is_file():
                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                        file_hashes.append(f"{file_path.name}:{file_hash}")
                except Exception:
                    pass
        
        return "|".join(file_hashes)
