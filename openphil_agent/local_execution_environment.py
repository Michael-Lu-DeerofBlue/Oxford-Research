"""
Local execution environment that runs code directly without Docker/HTTP.
Replaces the Flask server and container-based execution.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import git

from .generation.utils import FunctionSpec
from .aider.aider_controller import AiderController
from .aider.interpreter import Interpreter
from .task_environment import TaskEnvironment


def get_python_command() -> str:
    """Get the appropriate Python command for the current platform."""
    if sys.platform == "win32":
        return "python"
    else:
        return "python3"


class LocalExecutionEnvironment(TaskEnvironment):
    """
    Local execution environment that runs code directly without containers.
    Uses AiderController and Interpreter in-process.
    """

    def __init__(
        self,
        prompt: str,
        paper: str,
        work_dir: Path,
        aider_model: str = None,
        timeout: int = 3600,
        task_requirements_file: Optional[Path] = None,
    ):
        self.prompt = prompt
        self.paper = paper
        self.work_dir = Path(work_dir).resolve()
        
        if aider_model is None:
            aider_model = os.environ.get("AIDER_MODEL", "openrouter/openai/gpt-4o-mini")
        
        self.aider_model = aider_model
        self.timeout = timeout
        self.logs = []
        self.done = False
        self.answer_text = None
        self.answer_file = None
        self.error_history = []
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        if task_requirements_file and task_requirements_file.exists():
            self._install_requirements(task_requirements_file)
        
        try:
            self.git_repo = git.Repo(self.work_dir)
        except git.exc.InvalidGitRepositoryError:
            self.git_repo = git.Repo.init(self.work_dir)
        
        if self.aider_model.startswith("openrouter/"):
            if "OPENROUTER_API_KEY" in os.environ and "OPENAI_API_KEY" not in os.environ:
                os.environ["OPENAI_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
                self.logs.append("   Applied OpenRouter API key shim\n")
            
            if "OPENAI_API_BASE" not in os.environ:
                os.environ["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
                self.logs.append("   Applied OpenRouter base URL shim\n")
        
        chat_history_file = self.work_dir.parent / "logs" / "aider_chat_history"
        chat_history_file.parent.mkdir(parents=True, exist_ok=True)
        
        temperature = float(os.environ.get("AIDER_TEMPERATURE", "0.5"))
        
        self.aider_controller = AiderController(
            model_type=self.aider_model,
            chat_history_file=chat_history_file,
            work_dir=self.work_dir,
            temperature=temperature,
        )
        
        self.interpreter = None
        
        self.logs.append(f"   Agent starting with prompt: {self.prompt}\n")
    
    def _install_requirements(self, requirements_file: Path):
        """Install Python packages from requirements.txt."""
        self.logs.append(f"   Installing requirements from {requirements_file}\n")
        try:
            python_cmd = get_python_command()
            result = subprocess.run(
                [python_cmd, "-m", "pip", "install", "-r", str(requirements_file)],
                capture_output=True,
                timeout=300,  # 5 minutes max for installation
            )
            if result.returncode == 0:
                self.logs.append(f"   Requirements installed successfully\n")
            else:
                stderr = result.stderr.decode("utf-8", errors="replace")
                self.logs.append(f"   Warning: pip install had issues: {stderr[:200]}\n")
        except Exception as e:
            self.logs.append(f"   Warning: Could not install requirements: {e}\n")

    def available_actions(self):
        actions = {
            "instruct_aider": FunctionSpec(
                name="instruct_aider",
                json_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The instruction to give to the Aider coding assistant.",
                        }
                    },
                    "required": ["prompt"],
                    "additionalProperties": False,
                },
                description="Instruct the Aider AI coding assistant to write or modify code files.",
            ),
            "run_python_code": FunctionSpec(
                name="run_python_code",
                json_schema={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The python code to be executed.",
                        }
                    },
                    "required": ["code"],
                    "additionalProperties": False,
                },
                description="Execute Python code and return the output.",
            ),
            "run_bash_command": FunctionSpec(
                name="run_bash_command",
                json_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to be executed.",
                        }
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                description="Execute a bash command and return its output.",
            ),
            "return_all_files": FunctionSpec(
                name="return_all_files",
                json_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                description="Return all Python and PNG files in the work directory.",
            ),
            "submit_answer": FunctionSpec(
                name="submit_answer",
                json_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the figure file to submit as answer.",
                        }
                    },
                    "required": ["file_path"],
                    "additionalProperties": False,
                },
                description="Submit a figure file as the final answer. This marks the task as complete.",
            ),
        }
        return actions

    def reset(self):
        self.done = False
        self.answer_text = None
        self.answer_file = None
        self.logs = []
        return self.prompt

    def step(self, action: str, *args, **kwargs):
        if self.done:
            raise ValueError(
                "Cannot step in environment marked as done. Did you already submit the answer?"
            )

        if action == "instruct_aider":
            return self._action_instruct_aider(*args, **kwargs)
        elif action == "run_python_code":
            return self._action_run_python_code(*args, **kwargs)
        elif action == "run_bash_command":
            return self._action_run_bash_command(*args, **kwargs)
        elif action == "return_all_files":
            return self._action_return_all_files(*args, **kwargs)
        elif action == "submit_answer":
            return self._action_submit_answer(*args, **kwargs)
        else:
            raise ValueError(f"Invalid action: {action}")

    def _action_instruct_aider(self, prompt: str):
        """Instruct Aider to write or modify code."""
        self.logs.append(f"   Instructing Aider with: {prompt}\n")
        try:
            result = self.aider_controller.run(prompt)
            self.logs.append(f"   Aider completed\n")
            return "\n".join(self.logs)
        except Exception as e:
            error_msg = f"   Aider error: {str(e)}\n"
            self.logs.append(error_msg)
            return "\n".join(self.logs)

    def _action_run_python_code(self, code: str):
        """Execute Python code using the Interpreter."""
        self.logs.append(f"   Running Python code: {code[:100]}...\n")
        
        if self.interpreter is None:
            self.interpreter = Interpreter(
                working_dir=self.work_dir,
                timeout=self.timeout,
                agent_file_name="runfile.py",
            )
        
        try:
            result = self.interpreter.run(code, reset_session=True)
            self.logs.append(f"   Output: {result.term_out}\n")
            self.logs.append(f"   Execution time: {result.exec_time}s\n")
            if result.exc_type:
                self.logs.append(f"   Exception: {result.exc_type}\n")
            return "\n".join(self.logs)
        except Exception as e:
            error_msg = f"   Python execution error: {str(e)}\n"
            self.logs.append(error_msg)
            return "\n".join(self.logs)

    def _action_run_bash_command(self, command: str):
        """Execute a bash command."""
        if sys.platform == "win32" and "python3 " in command:
            command = command.replace("python3 ", "python ")
            self.logs.append(f"   [Windows] Converted python3 to python\n")
        
        self.logs.append(f"   Running bash command: {command}\n")
        
        env = os.environ.copy()
        if sys.platform == "win32":
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONFAULTHANDLER"] = "1"
        
        try:
            result = subprocess.run(
                command,
                cwd=self.work_dir,
                shell=True,
                capture_output=True,
                timeout=self.timeout,
                env=env,
            )
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            
            if result.returncode == 3221225477 or result.returncode == -1073741819:
                crash_msg = "Windows access violation (native crash). Possible causes: invalid PyBaMM API calls, missing DLLs, or incompatible native dependencies. Try simplifying the code or checking if PyBaMM works on Windows."
                if not stderr:
                    stderr = crash_msg
                else:
                    stderr = crash_msg + "\n" + stderr
                self.logs.append(f"   [Windows Crash Detected] {crash_msg}\n")
            
            if result.returncode != 0:
                if stderr:
                    error_signature = f"RC{result.returncode}:{stderr[:150]}"
                else:
                    error_signature = f"RC{result.returncode}:no_stderr"
                self.error_history.append(error_signature)
                if len(self.error_history) > 5:
                    self.error_history.pop(0)
            
            self.logs.append(f"   stdout: {stdout}\n")
            if stderr:
                self.logs.append(f"   stderr: {stderr}\n")
            self.logs.append(f"   return code: {result.returncode}\n")
            
            return {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {self.timeout}s"
            self.logs.append(f"   {error_msg}\n")
            return {"stdout": "", "stderr": error_msg, "returncode": -1}
        except Exception as e:
            error_msg = f"Bash execution error: {str(e)}"
            self.logs.append(f"   {error_msg}\n")
            return {"stdout": "", "stderr": error_msg, "returncode": -1}
    
    def has_repeated_error(self, threshold: int = 2) -> bool:
        """Check if the same error has occurred multiple times recently."""
        if len(self.error_history) < threshold:
            return False
        
        recent_errors = self.error_history[-threshold:]
        first_error = recent_errors[0]
        
        for error in recent_errors[1:]:
            if error[:100] != first_error[:100]:
                return False
        
        return True

    def _action_return_all_files(self):
        """Return all .py and .png files in the work directory."""
        files = {}
        png_exists = False
        
        for file_path in self.work_dir.iterdir():
            if file_path.is_file() and file_path.suffix in [".py", ".png"]:
                if file_path.suffix == ".png":
                    png_exists = True
                try:
                    if file_path.suffix == ".py":
                        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                    else:  # .png
                        with open(file_path, "rb") as f:
                            content = f.read().hex()
                    files[file_path.name] = content
                except Exception as e:
                    files[file_path.name] = f"Error reading file: {e}"
        
        if not png_exists:
            files["WARNING"] = "No PNG file found. There can be no answer submission."
        
        return files

    def _action_submit_answer(self, file_path: str):
        """Submit a file as the final answer."""
        full_path = self.work_dir / file_path
        if not full_path.exists():
            error_msg = f"File {file_path} does not exist in work directory"
            self.logs.append(f"   {error_msg}\n")
            return error_msg
        
        self.done = True
        self.answer_file = str(full_path)
        self.logs.append(f"   Submitted answer: {file_path}\n")
        return f"Answer submitted: {file_path}"

    def evaluate(self) -> float:
        """Evaluate the submitted answer."""
        if not self.done or self.answer_file is None:
            return 0.0
        return 1.0

    def deep_copy(self):
        """Deep copy not supported for local execution environment."""
        raise NotImplementedError("Deep copy not supported for LocalExecutionEnvironment")

    def get_logs(self):
        return self.logs

    def get_paper(self):
        return self.paper

    def cleanup(self):
        """Clean up resources."""
        if self.interpreter is not None:
            self.interpreter.cleanup_session()
