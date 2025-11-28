from abc import ABC, abstractmethod
from typing import Self

from human_eval.human_eval.evaluation import human_eval_score

from .generation.utils import FunctionSpec


class TaskEnvironment(ABC):
    @abstractmethod
    def available_actions(self) -> dict:
        """
        Return a dictionary of available actions that can be taken in the environment.
        """
        pass

    @abstractmethod
    def reset(self):
        """
        Reset the environment to its initial state and return the initial prompt.
        """
        pass

    @abstractmethod
    def step(self, action: str, *args, **kwargs) -> str:
        """
        Take a step in the environment by executing the given action.
        Return the result of the action.
        """
        pass

    @abstractmethod
    def evaluate(self) -> float:
        """
        Evaluate the current state of the environment and return a score.
        Only to be called by main loop, never by agent OR orchestration agent.
        """
        pass

    @abstractmethod
    def deep_copy(self) -> Self:
        """
        Create an independent copy of the environment. Only to be called by the orchestration agent.
        """
        pass

    @abstractmethod
    def get_logs(self) -> str:
        """
        Return a history of what has happened in this environment.
        """
        pass


class SimpleQuestionAnswerTextEnvironment(TaskEnvironment):
    def __init__(self, prompt, answer, *args, **kwargs):
        self.prompt = prompt
        self.answer = answer
        self.logs = ""

    def available_actions(self):
        return {
            "run_bash_command": None,
            "run_python_code": None,
            "view_files": None,
            "edit_files": None,
            "submit_file_as_answer": None,
            "submit_text_as_answer": None,
        }

    def reset(self):
        self.done = False
        self.answer_file = None
        self.answer_text = None
        return self.prompt

    def step(self, action, *args, **kwargs):
        if self.done:
            raise ValueError(
                "Cannot step in environment marked as done. Did you already submit the answer?"
            )

        if action == "run_bash_command":
            return self._action_run_bash_command(*args, **kwargs)
        elif action == "run_python_code":
            return self._action_run_python_code(*args, **kwargs)
        elif action == "view_files":
            return self._action_view_files(*args, **kwargs)
        elif action == "edit_files":
            return self._action_edit_files(*args, **kwargs)
        elif action == "submit_file_as_answer":
            return self._action_submit_file_as_answer(*args, **kwargs)
        elif action == "submit_text_as_answer":
            return self._action_submit_text_as_answer(*args, **kwargs)
        else:
            raise ValueError(f"Invalid action: {action}")

    def _action_run_bash_command(self, command):
        return f"Bash command '{command}' executed successfully"

    def _action_run_python_code(self, code):
        return "Python code executed successfully"

    def _action_view_files(self, path):
        return f"Here are the files at the location: {path}"

    def _action_edit_files(self, path, new_content):
        return f"File at {path} has been edited with new content: {new_content}"

    def _action_submit_file_as_answer(self, path):
        self.done = True
        self.answer_file = path
        return f"File at {path} has been submitted as the answer."

    def _action_submit_text_as_answer(self, text):
        self.done = True
        self.answer_text = text
        return f"Text '{text}' has been submitted as the answer."

    def evaluate(self) -> float:
        if not self.done:
            return 0.0
        if self.answer_file:
            print(
                f"Cant evaluate files yet, returning as incorrect regardless of contents of: '{self.answer_file}'"
            )
            return 0.0
        elif self.answer_text:
            print(f"Evaluating answer text '{self.answer_text}'")
            return 1.0 if self.answer_text == self.answer else 0.0
        else:
            raise RuntimeError(
                "Task marked as done but neither answer file nor answer text is set."
            )

    def deep_copy(self):
        return copy.deepcopy(self)

    def get_logs(self):
        return self.logs
