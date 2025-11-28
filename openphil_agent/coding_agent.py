import json
import os
from abc import ABC, abstractmethod
from typing import Optional

from .generation import query
from .task_environment import TaskEnvironment


def get_agent_model(agent_type: str = "default") -> str:
    """Get the model to use for a specific agent type from environment variables.
    
    Args:
        agent_type: Type of agent (e.g., 'llm', 'planning', 'decision', 'filemapper')
    
    Returns:
        Model string (e.g., 'openai/gpt-4o-mini')
    """
    env_var_map = {
        "llm": "LLM_AGENT_MODEL",
        "humaneval": "HUMANEVAL_AGENT_MODEL",
        "planning": "PLANNING_AGENT_MODEL",
        "decision": "DECISION_AGENT_MODEL",
        "filemapper": "FILEMAPPER_AGENT_MODEL",
        "default": "DEFAULT_AGENT_MODEL",
    }
    
    env_var = env_var_map.get(agent_type, "DEFAULT_AGENT_MODEL")
    model = os.environ.get(env_var)
    
    if model is None:
        model = os.environ.get("DEFAULT_AGENT_MODEL", "openai/gpt-4o-mini")
    
    return model


def clean_json_response(response: str) -> str:
    """Clean LLM response to extract valid JSON.
    
    Handles cases where the model wraps JSON in code fences or adds extra text.
    
    Args:
        response: Raw response from LLM
    
    Returns:
        Cleaned JSON string
    """
    if not response:
        return response
    
    response = response.strip()
    
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    
    if response.endswith("```"):
        response = response[:-3]
    
    response = response.strip()
    
    return response


class CodingAgent(ABC):
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
        **kwargs,
    ):
        """
        Run the agent on a task environment.
        The agents interactions will change the state of the task environment,
        so nothing needs to be returned.
        Note that the agent might be run multiple times on the same task environment,
        for varying lengths of time, this is decided by the orchestration agent.

        Args:
            task_env: TaskEnvironment
                The task environment to run the agent on.
            helper_message: Optional[str]
                A helper message that can be piped into the agent by the orchestration agent.
                This could be used to provide additional context or information to the
                agent about the current state of completion.
        """
        return None

    def run_on_task(
        self,
        task_env: TaskEnvironment,
        time_limit: Optional[int] = None,
        helper_message: Optional[str] = None,
        **kwargs,
    ):
        """
        Externally facing method to run the agent on a task environment.
        This method should not be overridden by subclasses, it is a wrapper
        to handle the time limit.
        The agents interactions will change the state of the task environment internally,
        so nothing needs to be returned.
        Note that the agent might be run multiple times on the same task environment,
        for varying lengths of time, this is decided by the orchestration agent.

        Args:
            task_env: TaskEnvironment
                The task environment to run the agent on.
            time_limit: Optional[int]
                The time limit for the agent to run in seconds.
            helper_message: Optional[str]
                A helper message that can be piped into the agent by the orchestration agent.
                This could be used to provide additional context or information to the
                agent about the current state of completion.
        """
        if time_limit is not None:
            # TODO: Implement time limit enforcement here
            print("Time limit enforcement not implemented yet.")
            self._run_on_task(task_env, helper_message, **kwargs)
        else:
            self._run_on_task(task_env, helper_message, **kwargs)


class AlwaysReturn42Agent(CodingAgent):
    """
    A simple agent that just submits 42 as the answer
    """

    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        inital_prompt = task_env.reset()
        print(f"Agent received prompt: {inital_prompt}")
        print(f"Agent received helper message: {helper_message}")
        print(f"Agent available actions: {task_env.available_actions().keys()}")
        obs = task_env.step("run_bash_command", "echo 'Hello World!'")
        print(f"Agent received observation: {obs}")
        obs = task_env.step("submit_text_as_answer", "42")
        print(f"Agent received observation: {obs}")
        return None


class ExampleCodeExecutionAgent(CodingAgent):
    """
    A simple agent that executes python code.
    """

    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        initial_prompt = task_env.reset()
        print(f"Agent available actions: {task_env.available_actions().keys()}")
        obs = task_env.step("run_python_code", "import os\nprint(os.getcwd())")
        print(f"Agent received observation: {obs}")

        obs = task_env.step("submit_text_as_answer", "Done!")
        print(f"Agent received observation: {obs}")
        return None


class LLMAgent(CodingAgent):
    """
    An LLM agent that has one shot at solving the task given in the task environment prompt using python code.
    """

    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
        **kwargs,
    ):
        initial_prompt = task_env.reset()
        print(f"Agent available actions: {task_env.available_actions().keys()}")

        if helper_message is None:
            helper_message = ""

        llm_message, llm_tool_call = query(
            system_message="""You are a tool-using helpful LLM agent. 
                Your task is to precisely solve that task that you are prompted to solve. 
                Do not hesitate to use the tools you are provided with to solve the task. 
                Note that should always follow through with every single step of the solution yourself, not just outline it.
                """,
            user_message=initial_prompt
            + "\n"
            + "Current state of the solution: "
            + "\n".join(task_env.get_logs())
            + "\n"
            + helper_message,
            tool_dict=task_env.available_actions(),
            tool_choice="run_python_code",
            model=get_agent_model("llm"),
            **kwargs,
        )

        # from the first tool call in the list, we extract the function name (first position in tuple) and the arguments (second position in tuple) and unpack the arguments
        # here: it will run code in interpreter since that is the only tool call that is allowed
        obs = task_env.step(llm_tool_call[0][0], **llm_tool_call[0][1])
        print(f"Agent received observation: {obs}")

        obs = task_env.step("submit_text_as_answer", "Done!")
        print(f"Agent received observation: {obs}")
        return None


class HumanEvalAgent(CodingAgent):
    """
    An LLM agent that has one shot at solving the task given in the task environment prompt using python code.
    """

    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
        **kwargs,
    ):
        initial_prompt = task_env.reset()
        print(f"Agent available actions: {task_env.available_actions().keys()}")
        if helper_message is None:
            helper_message = ""

        llm_message, llm_tool_call = query(
            system_message="""You are a tool-using helpful LLM agent. 
                Your task is to precisely solve the task that you are prompted to solve. 
                Do not hesitate to use the tools you are provided with to solve the task. 
                Note that should always follow through with every single step of the solution yourself, not just outline it. Explain your reasoning and steps in detail.
                """,
            user_message=initial_prompt
            + "\n"
            + "Previous actions and tried solutions: "
            + "\n".join(task_env.get_logs())
            + "\n"
            + helper_message,
            tool_dict=task_env.available_actions(),
            tool_choice="submit_text_as_answer",
            model=get_agent_model("humaneval"),
            **kwargs,
        )

        print(f"Agent returned the message: {llm_message}")
        print(f"Agent returned the tool call: {llm_tool_call}")

        # from the first tool call in the list, we extract the function name (first position in tuple) and the arguments (second position in tuple) and unpack the arguments
        obs = task_env.step(llm_tool_call[0][0], **llm_tool_call[0][1])
        print(f"Agent received observation: {obs}")
        return None


class BasicAiderAgent(CodingAgent):
    """
    The Basic Agent that can do the basic steps/actions
    """

    # This is the script that the agent will follow
    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        inital_prompt = task_env.reset()
        # print(f"Agent received prompt: {inital_prompt}")
        # print(f"Agent received helper message: {helper_message}")
        # print(f"Agent available actions: {task_env.available_actions()}")

        # This is an example usage of the gen_python_code action using AIDER

        obs = task_env.step("instruct_aider", inital_prompt)
        print(f"Instructed AIDER, the output is: {obs}")

        obs = task_env.step("run_bash_command", "python3 main.py")
        print(f"Agent ran the code, the output is: {obs}")

        obs = task_env.step("submit_text_as_answer", obs)
        print(f"Agent submitted the answer, the output is: {obs}")


class PlanningAgent(CodingAgent):
    """
    An LLM agent that provides a plan to solve the task given in the task environment.
    """

    def __init__(self, initial_prompt, task_env: TaskEnvironment):
        self.initial_prompt = initial_prompt
        self.task_env = task_env

    def _plan_on_prompt(
        self,
        step_prompt: str,
        use_paper: bool,
        helper_message: Optional[str] = None,
    ):
        initial_prompt = self.initial_prompt
        if step_prompt == "":
            step_prompt = "None"
        message = f"The ultimate goal is: {initial_prompt}\n Some additional information/prompt is: {step_prompt}"
        self.task_env.logs.append(
            f"Planning on the following prompt: {message}\n"
        )
        paper = self.task_env.get_paper()
        if use_paper:
            message = f"{message} \n Paper: {paper}"

        plan = query(
            system_message="""You are a tool-using helpful LLM agent. 
                Your task is to precisely come up with a plan that solves the task described in the prompt.  
                You can use the paper provided to you to help you with the task.
                Your should only provide a plan, not the actual solution. No code is needed.
                """,
            user_message=message,
            model=get_agent_model("planning"),
            temperature=0.2,
        )

        self.task_env.logs.append(f"   Generated plan: {plan}\n")

        if isinstance(plan, tuple):
            plan = plan[0]

        return plan

    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        # For the planning agent, simply return the plan
        return self._plan_on_prompt("")


class DecisionAgent(CodingAgent):
    """
    The Decision Agent that makes decisions based on the plan
    """

    def __init__(self, task_env: TaskEnvironment):
        self.task_env = task_env

    # This is the script that the agent will follow
    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        system_prompt = """
You are a Decision Making agent in a multi-agent research group. Your output should be JSON-only. 
Your task is to make a decision based on the prompt and provide responses strictly in valid JSON format with exactly three key-value pairs. 
Every output must be a single, self-contained JSON object containing only three items. 
The first key must be "action" and its value should be the action you choose. 
The second key must be "argument" and its value should be the argument that goes along with the action. 
The third key must be "use_log" and its value should be a boolean indicating whether to log the output. 
Reminder: Using log will help the next agent understand your decision-making process, but might cause context window issues.
When there is a file that you think you can run to test out the experiment, you should run it.
If you see a message like "No PNG file found. There can be no answer submission." in latest file mapping, you should not submit an answer.
If you see evaluator feedback indicating issues with the figure, address those issues before submitting.
Do not include any extra keys, markdown, or commentary outside the JSON object.
Example:
{
  "action": "instruct_aider",
  "argument": "Write a function that takes a list of integers and returns the sum.",
  "use_log": true
}
Or:
{
  "action": "run_bash_command",
  "argument": "python main.py",
  "use_log": false
}
Or:
{
  "action": "submit_answer",
  "argument": "figure.png",
  "use_log": false
}
Here are your available actions:
- instruct_aider (argument: a string which is the prompt to give to the AIDER agent. If you are not using the log, it should be a very specific instruction. IMPORTANT: Always request code with English comments and ASCII-only labels/text to avoid encoding issues.) 
- run_bash_command (argument: a string which is the command to run in the bash shell. If you want to run a python file, use "python main.py" - the system will auto-convert to the correct command for the platform.)
- submit_answer (argument: the filename of the figure to submit, e.g., "figure.png". Only use this when the evaluator confirms the figure is ready.)

Remember, your output must always be parseable as valid JSON and contain only three key-value pairs.

"""
        step_prompt = "With the following log from multi-agent research environment, make a decision a what to do next."
        log = task_env.logs
        message = f"{step_prompt}\n Log: {log}"

        self.task_env.logs.append(
            f"   Making a decision on the following prompt: {step_prompt}\n"
        )

        decision = query(
            system_message=system_prompt,
            user_message=message,
            model=get_agent_model("decision"),
            temperature=0.2,
        )

        if isinstance(decision, tuple):
            decision = decision[0]
        
        decision = clean_json_response(decision)
        
        self.task_env.logs.append(f"   Made decision (raw): {decision}\n")
        return decision

    def _make_decision(self):
        return self._run_on_task(self.task_env)


class FileMapperAgent(CodingAgent):
    """
    An agent that uses the LLM to read all the files in the provided JSON string and output a JSON
    mapping each filename to its summary.
    """

    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        files = task_env.step("return_all_files")

        # If files is already a dict, no need to parse
        if isinstance(files, dict):
            files_dict = files
        else:
            try:
                files_dict = json.loads(files)
            except Exception as e:
                return f"Error parsing file_json: {e}"

        summaries = {}
        # For each file, query the LLM to produce a concise summary.
        for filename, content in files_dict.items():
            if filename == "WARNING":
                summaries[filename] = content
                continue
            summary = query(
                system_message="You are a helpful LLM agent. Given a file's content, generate a concise summary describing its purpose and key implementation details.",
                user_message=content,
                model=get_agent_model("filemapper"),
                temperature=0.2,
            )
            # Check if the summary is a tuple, if it is, take the first element
            if isinstance(summary, tuple):
                summary = summary[0]
            summaries[filename] = summary.strip()

        mapping_json = json.dumps(summaries, indent=2)

        task_env.logs.append(
            f"A summary of the current availiable files are: {mapping_json}\n"
        )

        return mapping_json


class ReActAgent(CodingAgent):
    """
    The ReAct Agent that use other agents to solve the task
    """

    # This is the script that the agent will follow
    def _run_on_task(
        self,
        task_env: TaskEnvironment,
        helper_message: Optional[str] = None,
    ):
        self.task_env = task_env
        inital_prompt = task_env.reset()
        # The number of steps to run the ReAct Loop
        loop_steps = 20

        print(f"ReAct Agent received prompt: {inital_prompt}")
        print(f"ReAct Agent received helper message: {helper_message}")
        print(f"ReAct Agent available actions: {task_env.available_actions()}")
        self.planningAgent = PlanningAgent(inital_prompt, task_env)
        self.decisionAgent = DecisionAgent(task_env)
        self.fileMapperAgent = FileMapperAgent()

        # Plan using the PlanningAgent
        obs = self.planningAgent._plan_on_prompt("", use_paper=True)
        print(f"ReActAgent use PlanningAgent to generate a plan: {obs}")

        # Ask the DecisionAgent to make the decision about which action to take
        for i in range(loop_steps):
            obs = self.decisionAgent._make_decision()
            action, argument, use_log = self.decision_parser(obs)
            print(
                f"ReActAgent use DecisionAgent and made a decision: {action}; {argument}; {use_log}"
            )

            # Take the action
            fileMapped = False
            if action == "instruct_aider":
                if use_log:
                    argument = f"{argument} \n The log is: " + "\n".join(
                        task_env.get_logs()
                    )
                argument = f"{argument}"
                obs = task_env.step(action, argument)
                print(
                    f"ReActAgent did action {action}, received observation: {obs}"
                )
                # Call the FileMapperAgent to map the files in the current directory
                mapping = self.fileMapperAgent._run_on_task(task_env)
                print(f"FileMapperAgent produced mapping: {mapping}")
                fileMapped = True
            else:
                obs = task_env.step(action, argument)

            if fileMapped == False:
                print(
                    f"ReActAgent did action {action}, received observation: {obs}"
                )

            print(f"\n Loop {i+1} completed \n")

    def decision_parser(self, decision):
        """
        The ouput is a JSON object with three key-value pairs:
        {
            "action": "action_name",
            "argument": "argument_value"
            "use_log": boolean
        }
        combine the action and argument in to a single string like "{action}, {argument}"
        The action must be one of the available actions, if not, throw an error.
        If cannot be parsed as JSON, throw an error.
        """
        try:
            decision_dict = json.loads(decision)
            action = decision_dict.get("action")
            argument = decision_dict.get("argument")
            use_log = decision_dict.get("use_log")
            if not isinstance(use_log, bool):
                raise ValueError("use_log must be a boolean")
            if action not in self.task_env.available_actions():
                raise ValueError(f"Invalid action: {action}")
            combined_action_argument = f"{action}, {argument}, {use_log}"
            decision = combined_action_argument
            return action, argument, use_log

        except json.JSONDecodeError as e:
            print(f"❌ Decision parsing error: {e}")
            print(f"Raw decision output: {repr(decision)}")
            print(f"Decision length: {len(decision) if decision else 0}")
            raise ValueError(f"Decision output is not valid JSON: {e}\nRaw output: {decision[:200] if decision else 'empty'}")
