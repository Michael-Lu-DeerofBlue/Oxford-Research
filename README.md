# Oxford Research Agentic AI Framework

This is a part of the ongoing Oxford Research project to establish a benchmark for evaluating Large Language Models (LLMs) in data-poor scientific domains, funded by Open Philanthropy. This framework allows LLMs to autonomously plan, execute, and iterate on complex computational science tasks using an agentic architecture integrated with AI-powered code editing. A poster describing this project can be found [here](ResearchPoster.pdf). This poster is used for Michael Lu's presentation at Swarthmore College Computer Science Senior Comphrehensive.

## Overview

This framework provides a simplified, local execution environment for running AI-powered coding tasks. The system uses a planning and decision-making loop with Aider integration to autonomously complete programming challenges.

**Key Features:**
- Local execution environment
- Configurable LLM models via environment variables
- OpenRouter API integration for flexible model selection
- Aider AI coding assistant with full OpenRouter support
- ReAct-style agent loop for autonomous task completion
- Support for multiple task types (code generation, engineering tasks)

## Quick Start

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Michael-Lu-DeerofBlue/Oxford-Research.git
cd Oxford-Research
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenRouter API key:
```bash
# Linux/Mac
export OPENROUTER_API_KEY="your-openrouter-api-key"

# Windows PowerShell
$env:OPENROUTER_API_KEY = "your-openrouter-api-key"
```

### Running a Task

Run a task using the CLI:

```bash
python -m openphil_agent.cli --task-dir tasks/development/fibonacci_code
python -m openphil_agent.cli --task-dir tasks/development/task_eng_surface_waves
```

The system will:
1. Display the model configuration being used
2. Create a planning strategy
3. Execute a ReAct loop to complete the task
4. Use Aider to write/modify code as needed
5. Run bash commands and Python code
6. Submit the final answer

## Model Configuration

The system supports configurable models for different components via environment variables.

### Agent Models

Agents use the format: `<provider>/<model>` (e.g., `openai/gpt-4o-mini`)

**Environment Variables:**
- `DEFAULT_AGENT_MODEL` - Default model for all agents (default: `openai/gpt-4o-mini`)
- `LLM_AGENT_MODEL` - Override for LLMAgent
- `HUMANEVAL_AGENT_MODEL` - Override for HumanEvalAgent
- `PLANNING_AGENT_MODEL` - Override for PlanningAgent
- `DECISION_AGENT_MODEL` - Override for DecisionAgent
- `FILEMAPPER_AGENT_MODEL` - Override for FileMapperAgent

**Example:**
```bash
# Linux/Mac
export DEFAULT_AGENT_MODEL="openai/gpt-4o"
export PLANNING_AGENT_MODEL="openai/gpt-4o"
export DECISION_AGENT_MODEL="openai/gpt-4o-mini"

# Windows PowerShell
$env:DEFAULT_AGENT_MODEL = "openai/gpt-4o"
$env:PLANNING_AGENT_MODEL = "openai/gpt-4o"
$env:DECISION_AGENT_MODEL = "openai/gpt-4o-mini"
```

### Aider Model

Aider uses OpenRouter format: `openrouter/<provider>/<model>`

**Environment Variables:**
- `AIDER_MODEL` - Model for Aider (default: `openrouter/openai/gpt-4o-mini`)
- `AIDER_TEMPERATURE` - Temperature for Aider (default: `0.5`)
- `AIDER_MAP_TOKENS` - Tokens for repository map (default: `4096`)
- `AIDER_MAX_CHAT_HISTORY_TOKENS` - Max chat history (default: `32768`)

**Example:**
```bash
# Linux/Mac
export AIDER_MODEL="openrouter/openai/o3-mini"
export AIDER_TEMPERATURE="0.4"

# Windows PowerShell
$env:AIDER_MODEL = "openrouter/openai/o3-mini"
$env:AIDER_TEMPERATURE = "0.4"
```

**Recommended Aider Models:**
- `openrouter/openai/o3-mini` - Best balance of capability and cost
- `openrouter/openai/o1-mini` - Deeper reasoning for complex tasks
- `openrouter/openai/gpt-4o` - Fast and capable
- `openrouter/anthropic/claude-3.7-sonnet` - Alternative to OpenAI models

### Configuration Display

When you start a task, the system displays the current configuration:

```
============================================================
MODEL CONFIGURATION
============================================================
Aider Model: openrouter/openai/o3-mini (temperature: 0.4)
Planning Agent: openai/gpt-4o
Decision Agent: openai/gpt-4o-mini
LLM Agent: openai/gpt-4o-mini
HumanEval Agent: openai/gpt-4o-mini
FileMapper Agent: openai/gpt-4o-mini
OPENROUTER_API_KEY present: True
============================================================
```

## Architecture

### Components

**1. CLI Entry Point (`openphil_agent/cli.py`)**
- Command-line interface for running tasks
- Handles argument parsing and configuration
- Displays model configuration at startup

**2. AIScientist (`openphil_agent/ai_scientist.py`)**
- Main orchestrator for task execution
- Creates LocalExecutionEnvironment
- Runs the ReAct agent loop

**3. LocalExecutionEnvironment (`openphil_agent/local_execution_environment.py`)**
- Local execution environment (no containers)
- Integrates Aider for code editing
- Provides actions: instruct_aider, run_bash_command, run_python_code, submit_answer
- Handles OpenRouter API key configuration

**4. Agents (`openphil_agent/coding_agent.py`)**
- **PlanningAgent**: Creates high-level plans for tasks
- **DecisionAgent**: Makes decisions in the ReAct loop
- **LLMAgent**: General-purpose LLM interactions
- **HumanEvalAgent**: Specialized for HumanEval benchmark
- **FileMapperAgent**: Maps and understands file structures
- **ReActAgent**: Implements the ReAct loop

**5. Aider Integration (`openphil_agent/aider/`)**
- **AiderController**: Manages Aider sessions
- **Interpreter**: Executes Python code

**6. Task Environment (`openphil_agent/task_environment.py`)**
- Abstract base class for task environments
- SimpleQuestionAnswerTextEnvironment for basic tasks

### Execution Flow

1. **Initialization**: CLI loads configuration and creates AIScientist
2. **Planning**: PlanningAgent creates a strategy for the task
3. **ReAct Loop**: 
   - DecisionAgent chooses next action
   - LocalExecutionEnvironment executes action
   - Results are logged and fed back to DecisionAgent
   - Loop continues until task is complete or max iterations reached
4. **Completion**: Final answer is submitted and evaluated

### Available Actions

The LocalExecutionEnvironment provides these actions:

- **instruct_aider**: Give instructions to Aider to write/modify code
- **run_bash_command**: Execute bash commands in the work directory
- **run_python_code**: Execute Python code
- **return_all_files**: Get list of all files in work directory
- **submit_answer**: Submit the final answer (file path)

## Tasks

Tasks are defined in the `tasks/` directory with the following structure:

```
tasks/
├── development/
│   ├── fibonacci_code/
│   │   ├── prompt.md          # Task description
│   │   ├── answer.md          # Expected answer (optional)
│   │   └── paper_markdown.md  # Additional context (optional)
│   └── ...
└── engineering/
    └── ...
```

### Example Tasks

**Fibonacci Code** (`tasks/development/fibonacci_code/`)
- Write a Python script to compute the 15th Fibonacci number
- Simple code generation task

**PyBaMM Tasks** (`tasks/development/task_eng_pybamm_*`)
- Engineering tasks involving battery modeling
- More complex tasks requiring understanding of scientific code

### Creating New Tasks

1. Create a new directory under `tasks/development/` or `tasks/engineering/`
2. Add a `prompt.md` file with the task description
3. Optionally add `answer.md` with expected output
4. Run with: `python -m openphil_agent.cli --task-dir tasks/your_task_name`

## Configuration Files

**MODEL_CONFIGURATION.md** - Detailed model configuration guide with examples and troubleshooting

**requirements.txt** - Python dependencies for the main system

**requirements_task.txt** - Additional dependencies for specific tasks

## Development

### Project Structure

```
openphil_agent/
├── __init__.py
├── cli.py                              # CLI entry point
├── ai_scientist.py                     # Main orchestrator
├── local_execution_environment.py      # Local execution environment
├── coding_agent.py                     # Agent implementations
├── task_environment.py                 # Task environment base classes
├── self_evaluator.py                   # Evaluation logic
├── aider/                              # Aider integration
│   ├── aider_controller.py
│   └── interpreter.py
└── generation/                         # LLM backend
    ├── backend_openai.py
    └── utils.py
```

### Running Locally

1. Set environment variables for model configuration
2. Run a task: `python -m openphil_agent.cli --task-dir tasks/development/fibonacci_code`
3. Check output in `run_output/<task_name>/`

### Customization

**Change Models:**
Set environment variables before running (see Model Configuration section)

**Adjust Aider Parameters:**
```bash
export AIDER_TEMPERATURE="0.3"        # Lower for more deterministic output
export AIDER_MAP_TOKENS="8192"        # Increase for larger codebases
```

**Modify Agent Behavior:**
Edit agent implementations in `openphil_agent/coding_agent.py`

## Troubleshooting

### API Key Issues

**Error: "The api_key client option must be set"**
- Make sure `OPENROUTER_API_KEY` is set in your environment
- Verify the key is valid at https://openrouter.ai/keys

### Model Configuration Issues

**Aider using wrong model:**
- Check that `AIDER_MODEL` uses OpenRouter format: `openrouter/<provider>/<model>`
- Verify the model configuration display at startup

**Agents using wrong model:**
- Check that agent models use provider-prefixed format: `<provider>/<model>`
- Set `DEFAULT_AGENT_MODEL` to change all agents at once

### JSON Parsing Errors

**Error: "Expecting value: line 1 column 1"**
- This usually means the DecisionAgent model is not following JSON format
- Try using `gpt-4o-mini` for DecisionAgent (better at structured output)
- The system automatically cleans JSON responses wrapped in code fences

### Task Execution Issues

**Task times out or doesn't complete:**
- Check the logs in `run_output/<task_name>/logs/`
- Increase max iterations if needed (default: 40)
- Try using more capable models (e.g., `gpt-4o` instead of `gpt-4o-mini`)

## Security

**API Key Safety:**
- Never commit API keys to the repository
- Use environment variables for all secrets
- Regenerate keys if accidentally exposed

## Cost Optimization

**Tips for reducing API costs:**
1. Use `gpt-4o-mini` for agents (cheaper, still capable)
2. Use `o3-mini` for Aider instead of `o1` (better cost/performance)
3. Set lower `AIDER_MAP_TOKENS` for smaller codebases
4. Use `gpt-4o-mini` for DecisionAgent (makes many calls)

**Guidelines:**
- Follow existing code style
- Test changes with multiple tasks
- Update documentation for new features
- Keep the architecture simple and maintainable

## License

See LICENSE file for details.

## Acknowledgments

- Built on [Aider](https://aider.chat/) for AI-powered code editing
- Uses [OpenRouter](https://openrouter.ai/) for flexible LLM access
- Inspired by ReAct and AI Scientist research

## Support

For issues or questions:
- Check MODEL_CONFIGURATION.md for detailed configuration help
- Review troubleshooting section above
- Open an issue on GitHub

---

**Note:** This is the refactored simplified architecture. The old Docker-in-Docker implementation has been removed for simplicity and maintainability.
