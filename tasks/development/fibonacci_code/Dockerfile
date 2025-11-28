FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04

ENV CUDA_PATH /usr/local/cuda
ENV CUDA_INCLUDE_PATH /usr/local/cuda/include
ENV CUDA_LIBRARY_PATH /usr/local/cuda/lib64

# Set timezone
ENV TZ=Europe/London DEBIAN_FRONTEND=noninteractive

# Add Python 3.8 to Ubuntu 22.04 and install dependencies
RUN apt update
RUN apt install -y software-properties-common && add-apt-repository ppa:deadsnakes/ppa
RUN apt install -y \
    git \
    python3.11 \
    python3-pip \
    python3.11-venv \
    python3-setuptools \
    python3-wheel \
    docker.io \
    python3.11-dev \
    build-essential

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN update-alternatives --set python3 /usr/bin/python3.11

# Create local user
# https://jtreminio.com/blog/running-docker-containers-as-current-host-user/
ARG UID
ARG GID
RUN if [ ${UID:-0} -ne 0 ] && [ ${GID:-0} -ne 0 ]; then \
    groupadd -g ${GID} duser &&\
    useradd -l -u ${UID} -g duser duser &&\
    install -d -m 0755 -o duser -g duser /home/duser &&\
    chown --changes --silent --no-dereference --recursive ${UID}:${GID} /home/duser \
    ;fi

USER duser
WORKDIR /home/duser

# Install pip
ENV PATH="/home/duser/.local/bin:$PATH"
RUN python3 -m pip install --upgrade pip

# Install Python packages
ARG TASK_DIR
COPY --chown=duser:duser ${TASK_DIR}/requirements_merged.txt /home/duser/requirements_merged.txt
RUN python3 -m pip install -r requirements_merged.txt

# Copy in the agent code / task_docker
RUN mkdir -p /home/duser/project
WORKDIR /home/duser/project
ARG AGENT_DIR
COPY --chown=duser:duser ${AGENT_DIR}/task_docker_template/* ./

# make a logs file
RUN mkdir -p /home/duser/project/logs
RUN mkdir -p /home/duser/project/logs/aider_chat_history

# make the aider work dir
RUN mkdir -p /home/duser/project/aider_work_dir
COPY --chown=duser:duser ${TASK_DIR}/* ./aider_work_dir/
