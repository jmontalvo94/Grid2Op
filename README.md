# Grid2Op
[![Downloads](https://pepy.tech/badge/grid2op)](https://pepy.tech/project/grid2op)
[![PyPi_Version](https://img.shields.io/pypi/v/grid2op.svg)](https://pypi.org/project/Grid2Op/)
[![PyPi_Compat](https://img.shields.io/pypi/pyversions/grid2op.svg)](https://pypi.org/project/Grid2Op/)
[![LICENSE](https://img.shields.io/pypi/l/grid2op.svg)](https://www.mozilla.org/en-US/MPL/2.0/)
[![Documentation Status](https://readthedocs.org/projects/grid2op/badge/?version=latest)](https://grid2op.readthedocs.io/en/latest/?badge=latest)
[![circleci](https://circleci.com/gh/rte-france/Grid2Op.svg?style=shield)](https://circleci.com/gh/rte-france/Grid2Op)
[![discord](https://discord.com/api/guilds/698080905209577513/embed.png)]( https://discord.gg/cYsYrPT)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/rte-france/Grid2Op/master)

Grid2Op is a plateform, built with modularity in mind, that allows to perform powergrid operation.
And that's what it stands for: Grid To Operate.
Grid2Op acts as a replacement of [pypownet](https://github.com/MarvinLer/pypownet) 
as a library used for the Learning To Run Power Network [L2RPN](https://l2rpn.chalearn.org/). 

This framework allows to perform most kind of powergrid operations, from modifying the setpoint of generators,
to load shedding, performing maintenance operations or modifying the *topology* of a powergrid
to solve security issues.

Official documentation: the official documentation is available at 
[https://grid2op.readthedocs.io/](https://grid2op.readthedocs.io/).

*   [1 Installation](#installation)
    *   [1.1 Setup a Virtualenv (optional)](#setup-a-virtualenv-optional)
    *   [1.2 Install from source](#install-from-source)
    *   [1.3 Install from PyPI](#install-from-pypi)
    *   [1.4 Install for contributors](#install-for-contributors)
    *   [1.5 Docker](#docker)
*   [2 Main features of Grid2Op](#main-features-of-grid2op)
*   [3 Getting Started](#getting-started)
    *   [0 Basic features](getting_started/0_basic_functionalities.ipynb)
    *   [1 BaseObservation Agents](getting_started/1_Observation_Agents.ipynb)
    *   [2 BaseAction Grid Manipulation](getting_started/2_Action_GridManipulation.ipynb)
    *   [3 Training An BaseAgent](getting_started/3_TrainingAnAgent.ipynb)
    *   [4 Study Your BaseAgent](getting_started/4_StudyYourAgent.ipynb)
*   [4 Documentation](#documentation)
*   [5 Test and known issues](#tests-and-known-issues)
*   [6 License information](#license-information)

# Installation
## Requirements:
*   Python >= 3.6

## Setup a Virtualenv (optional)
### Create a virtual environment 
```commandline
cd my-project-folder
pip3 install -U virtualenv
python3 -m virtualenv venv_grid2op
```
### Enter virtual environment
```commandline
source venv_grid2op/bin/activate
```

## Install from source
```commandline
git clone https://github.com/rte-france/Grid2Op.git
cd Grid2Op
pip3 install -U .
cd ..
```

## Install from PyPI
```commandline
pip3 install grid2op
```

## Install for contributors
```commandline
git clone https://github.com/rte-france/Grid2Op.git
cd Grid2Op
pip3 install -e .
pip3 install -e .[optional]
pip3 install -e .[docs]
```

## Docker
Grid2Op docker containers are available on [dockerhub](https://hub.docker.com/r/bdonnot/grid2op/tags).

To install the latest Grid2Op container locally, use the following:
```commandline
docker pull bdonnot/grid2op:latest
```

# Main features of Grid2Op
## Core functionalities
Built with modulartiy in mind, Grid2Op acts as a replacement of [pypownet](https://github.com/MarvinLer/pypownet) 
as a library used for the Learning To Run Power Network [L2RPN](https://l2rpn.chalearn.org/). 

Its main features are:
* emulates the behavior of a powergrid of any size at any format (provided that a *backend* is properly implemented)
* allows for grid modifications (active and reactive load values, generator voltages setpoints and active production)
* allows for maintenance operations and powergrid topological changes
* can adopt any powergrid modeling, especially Alternating Current (AC) and Direct Current (DC) approximation to 
  when performing the compitations
* supports changes of powerflow solvers, actions, observations to better suit any need in performing power system operations modeling
* has an RL-focused interface, compatible with [OpenAI-gym](https://gym.openai.com/): same interface for the
  Environment class.
* parameters, game rules or type of actions are perfectly parametrizable
* can adapt to any kind of input data, in various format (might require the rewriting of a class)

## Powerflow solver
Grid2Op relies on an open source powerflow solver ([PandaPower](https://www.pandapower.org/)),
but is also compatible with other *Backend*. If you have at your disposal another powerflow solver, 
the documentation of [grid2op/Backend](grid2op/Backend/Backend.py) can help you integrate it into a proper "Backend"
and have Grid2Op using this powerflow instead of PandaPower.

# Getting Started
Some Jupyter notebook are provided as tutorials for the Grid2Op package. They are located in the 
[getting_started](getting_started) directories. 

These notebooks will help you in understanding how this framework is used and cover the most
interesting part of this framework:

* [00_Introduction](getting_started/00_Introduction.ipynb) and [00_SmallExample](getting_started/00_SmallExample.ipynb) 
  describe what is 
  adressed by the grid2op framework (with a tiny introductions to both power systems and reinforcement learning) 
  and give and introductory example to a small powergrid manipulation.
* [01_Grid2opFramework](getting_started/01_Grid2opFramework.ipynb) covers the basics 
  of the
  Grid2Op framework. It also covers how to create a valid environment and how to use the 
  `Runner` class to assess how well an agent is performing rapidly.
* [O2_Observation](getting_started/02_Observation.ipynb) details how to create 
  an "expert agent" that will take pre defined actions based on the observation it gets from 
  the environment. This Notebook also covers the functioning of the BaseObservation class.
* [03_Action](getting_started/03_Action.ipynb) demonstrates 
  how to use the BaseAction class and how to manipulate the powergrid.
* [04_TrainingAnAgent](getting_started/04_TrainingAnAgent.ipynb) shows how to get started with 
  reinforcement learning in the Grid2Op framework. It will use the code provided by Abhinav Sagar
  available on [his blog](https://towardsdatascience.com/deep-reinforcement-learning-tutorial-with-open-ai-gym-c0de4471f368) 
  or on [his github repository](https://github.com/abhinavsagar/Reinforcement-Learning-Tutorial). This code will
  be adapted (only minor changes, most of them to fit the shape of the data) 
  and a (D)DQN will be trained on this problem.
* [05_StudyYourAgent](getting_started/05_StudyYourAgent.ipynb) shows how to study an BaseAgent, for example
  the methods to reload a saved experiment, or to plot the powergrid given an observation for
  example. This is an introductory notebook. More user friendly graphical interface should
  come soon.
* [06_Redispatching](getting_started/06_Redispatching.ipynb) explains what is the "redispatching" from the point 
  of view of a company who's in charge of keeping the powergrid safe (aka a Transmission System Operator) and how to 
  manipulate this concept in grid2op. Redispatching allows you to perform **continuous** actions on the powergrid 
  problem.
* [07_MultiEnv](getting_started/07_MultiEnv.ipynb) details how grid2op natively support a single agent interacting
  with multiple environments at the same time. This is particularly handy to train "asynchronous" agent in the 
  Reinforcement Learning community for example.
* [08_PlottingCapabilities](getting_started/08_PlottingCapabilities.ipynb) shows you the different ways with which you 
  can represent (visually) the grid your agent interact with. A renderer is available like in many open AI gym 
  environment. But you also have the possibility to post process an agent and make some movies out of it, and we also
  developed a Graphical User Interface (GUI) called "[grid2viz](https://github.com/mjothy/grid2viz)" that allows
  to perform in depth study of your agent's behaviour on different scenarios and even to compare it with baselines. 
* [09_EnvironmentModifications](getting_started/09_EnvironmentModifications.ipynb) elaborates on the maintenance, hazards
  and attacks. All three of these represents external events that can disconnect some powerlines. This notebook
  covers how to spot when such things happened and what can be done when the maintenance or the attack is over.
  
Try them out in your own browser without installing 
anything with the help of mybinder: 
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/rte-france/Grid2Op/master)

# Documentation

The official documentation is available at 
[https://grid2op.readthedocs.io/](https://grid2op.readthedocs.io/).

## Build the documentation locally

A copy of the documentation can be built if the project is installed *from source*:
you will need Sphinx, a Documentation building tool, and a nice-looking custom
[Sphinx theme similar to the one of readthedocs.io](https://sphinx-rtd-theme.readthedocs.io/en/latest/). These
can be installed with:
```commandline
pip3 install -U grid2op[docs]
```
This installs both the Sphinx package and the custom template. 

Then, on systems where `make` is available (mainly gnu-linux and macos) the documentation can be built with the command:
```commandline
make html
```

For windows, or systems where `make` is not available, the command:
```commandline
sphinx-build -b html docs documentation
```


This will create a "documentation" subdirectory and the main entry point of the document will be located at 
[index.html](documentation/html/index.html).

It is recommended to build this documentation locally, for convenience.
For example, the  "getting started" notebooks referenced some pages of the help.

<!-- sphinx-build -b html docs documentation-->

# Tests and known issues

## Tests performed currently
Grid2op is currently tested on windows, linux and macos.

The unit tests includes testing, on linux machines the correct integration of grid2op with:

- python 3.6
- python 3.7
- python 3.8
- python 3.9

Note that, at time of writing, "numba" which accelerates the computation of the powerflow for the default 
"powerflow solver" is not available for python 3.9 (more information at https://github.com/numba/numba/issues/6345).

On all of these cases, we tested grid2op on all available numpy version >= 1.18.

## Known issue

Due to the underlying behaviour of the "multiprocessing" package on windows based python versions,
the "multiprocessing" of the grid2op "Runner" is not supported on windows. This might change in the future, 
but it is currently not on our priorities.

## Perform tests locally
Provided that Grid2Op is installed *from source*:

### Install additional dependencies
```commandline
pip3 install -U grid2op[optional]
```
### Launch tests
```commandline
cd grid2op/tests
python3 -m unittest discover
```

# License information
Copyright 2019-2020 RTE France

    RTE: http://www.rte-france.com

This Source Code is subject to the terms of the Mozilla Public License (MPL) v2 also available 
[here](https://www.mozilla.org/en-US/MPL/2.0/)

# Contributing

We welcom contribution from everyone. They can take the form of pull requests for smaller changed. 
In case of a major change (or if you have a doubt on what is "a small change"), please open an issue first 
to discuss what you would like to change.

Code in the contribution should pass all the tests, have some dedicated tests for the new feature
and documentation.
