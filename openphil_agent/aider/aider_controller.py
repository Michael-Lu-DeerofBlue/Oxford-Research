import re
from pathlib import Path
import shutil
import git

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from aider.repo import GitRepo

PromptType = str | dict | list

def compile_prompt_to_md(prompt: PromptType, _header_depth: int = 1) -> str:
    if isinstance(prompt, str):
        return prompt.strip() + "\n"
    elif isinstance(prompt, list):
        return "\n".join([f"- {s.strip()}" for s in prompt] + ["\n"])

    out = []
    header_prefix = "#" * _header_depth
    for k, v in prompt.items():
        out.append(f"{header_prefix} {k}\n")
        out.append(compile_prompt_to_md(v, _header_depth=_header_depth + 1))
    return "\n".join(out)

class AiderController:

    def __init__(
        self,
        model_type: str,
        chat_history_file: Path,
        work_dir: Path,
        temperature: float,
        map_tokens: int = 4096,
        max_chat_history_tokens: int = 8 * 4096,
        max_reflections: int = 5,
    ):

        self.model_type = model_type
        self.chat_history_file = chat_history_file
        self.work_dir = work_dir
        self.temperature = temperature
        self.map_tokens = map_tokens
        self.max_chat_history_tokens = max_chat_history_tokens
        self.max_reflections = max_reflections

        self.chat_history_file = self.chat_history_file.joinpath("history.log")
        
        self.io = InputOutput(
            yes=True,  # Say yes to every suggestion aider makes
            chat_history_file=self.chat_history_file,  # Log the chat here
            input_history_file="/dev/null",  # Don't log the "user input"
        )

        self.model = Model(self.model_type)
        self.model.max_chat_history_tokens = self.max_chat_history_tokens

        # Setup the aider work dir
        work_dir = self.work_dir.resolve()
        print(f"Work dir exists: {work_dir.exists()}")
        print(f"Creating git repo in {work_dir}")
        _ = git.Repo.init(work_dir)
        
        aider_ignore_file = work_dir / ".aiderignore"
        if not aider_ignore_file.exists():
            aider_ignore_file = None
        
        self.git_repo = GitRepo(
            io=self.io, fnames=None, git_dname=work_dir, aider_ignore_file=aider_ignore_file
        )

        self.coder = Coder.create(
            main_model=self.model,
            io=self.io,
            repo=self.git_repo,
            map_tokens=self.map_tokens,  # No. tokens to create repo map
            stream=False,
            auto_commits=False,  # No git committing
            auto_test=False,  # not testing automatically
            test_cmd=None,
            edit_format="diff",
            # verbose=True,
            detect_urls=False,  # prevent it scarping from the web, FOR NOW
        )

        self.coder.temperature = self.temperature
        self.coder.max_reflections = self.max_reflections
        self.coder.show_announcements()

    def run(self, prompt: str) -> str:
        english_instruction = """CRITICAL INSTRUCTIONS - FOLLOW EXACTLY:
1. Write ALL code with English comments ONLY - NO Chinese, Japanese, or other non-ASCII text
2. Use ASCII-only text for ALL labels, axis titles, print statements, and variable names
3. For matplotlib plots: ALWAYS add these lines at the top:
   import matplotlib
   matplotlib.use('Agg')
4. ALWAYS use plt.savefig('figure.png') to save plots - NEVER use plt.show()
5. Do NOT ask for confirmation - apply edits directly
6. Output ONLY the SEARCH/REPLACE blocks - no explanatory text

"""
        full_prompt = english_instruction + prompt
        
        # TODO: currently disabled "preproc" flag because it caused all files
        # in repo to be added to context and overloaded it
        output_code = self.coder.run(
            compile_prompt_to_md(full_prompt), preproc=False
        )
        
        return output_code
    