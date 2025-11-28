# Directory Structure and Information

There are separate directory for `development/` and `production/` tasks. 

Each task is in a sub-directory with naming convention `task_[SUBJECT]_[NAME]` where `[SUBJECT]` should be one of the following:
- `eng`
- `phys`
- `chem`
- `bio`
- `biochem`
- ...

Each sub-directory `task_[SUBJECT]_[NAME]` is structured as follows:

```
task_[SUBJECT]_[NAME]/
├── README.md
├── data
│             ├── data1.csv
│             └── data2.csv
├── docs
│             └── docs.pdf
├── extra_links.json
├── ground_truth_code
│             ├── code1.ipynb
│             ├── code2.py
├── paper.pdf
├── paper_markdown.md
├── prompt.md
├── requirements.txt
└── supporting.pdf
```

- `paper_markdown.md` contains a markdown version of the publication
- `README.md` contains some useful info for agent team about running the task
- `data/` this contains any extra datafiles that the agent/human needs
- `extra_links.json` contains info about where docs are located on the web and any links to be black listed
- `prompt.md` is a markdown file with the task definition
- `requirements.txt` this contains python requirements that need to be installed
- `ground_truth_code/` [OPTIONAL] contains correct code and should not be shown to the agent/human
- `docs/` [OPTIONAL] this contains either markdown or pdf of codebase documentation. 