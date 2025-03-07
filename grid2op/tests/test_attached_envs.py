# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Grid2Op, Grid2Op a testbed platform to model sequential decision making in power systems.


import warnings
import unittest
import grid2op

from grid2op.Action.PowerlineSetAction import PowerlineSetAction
from grid2op.Action.PlayableAction import PlayableAction
from grid2op.Observation.CompleteObservation import CompleteObservation
from grid2op.Action.DontAct import DontAct

import pdb

# TODO refactor to have 1 base class, maybe


class TestL2RPNNEURIPS2020_Track1(unittest.TestCase):
    def setUp(self) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.env = grid2op.make("l2rpn_neurips_2020_track1", test=True)

    def test_elements(self):
        assert self.env.n_sub == 36
        assert self.env.n_line == 59
        assert self.env.n_load == 37
        assert self.env.n_gen == 22
        assert self.env.n_storage == 0

    def test_opponent(self):
        assert issubclass(self.env._opponent_action_class, PowerlineSetAction)
        assert self.env._opponent_action_space.n == self.env.n_line

    def test_action_space(self):
        assert issubclass(self.env.action_space.subtype, PlayableAction)
        assert self.env.action_space.n == 494

    def test_observation_space(self):
        assert issubclass(self.env.observation_space.subtype, CompleteObservation)
        assert self.env.observation_space.n == 1266


class TestL2RPNNEURIPS2020_Track2(unittest.TestCase):
    def setUp(self) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.env = grid2op.make("l2rpn_neurips_2020_track2", test=True)

    def test_elements(self):
        assert self.env.n_sub == 118
        assert self.env.n_line == 186
        assert self.env.n_load == 99
        assert self.env.n_gen == 62
        assert self.env.n_storage == 0

    def test_opponent(self):
        assert issubclass(self.env._opponent_action_class, DontAct)
        assert self.env._opponent_action_space.n == 0

    def test_action_space(self):
        assert issubclass(self.env.action_space.subtype, PlayableAction)
        assert self.env.action_space.n == 1500

    def test_observation_space(self):
        assert issubclass(self.env.observation_space.subtype, CompleteObservation)
        assert self.env.observation_space.n == 3868


class TestL2RPN_CASE14_SANDBOX(unittest.TestCase):
    def setUp(self) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.env = grid2op.make("l2rpn_case14_sandbox", test=True)

    def test_elements(self):
        assert self.env.n_sub == 14
        assert self.env.n_line == 20
        assert self.env.n_load == 11
        assert self.env.n_gen == 6
        assert self.env.n_storage == 0

    def test_opponent(self):
        assert issubclass(self.env._opponent_action_class, DontAct)
        assert self.env._opponent_action_space.n == 0

    def test_action_space(self):
        assert issubclass(self.env.action_space.subtype, PlayableAction)
        assert self.env.action_space.n == 160

    def test_observation_space(self):
        assert issubclass(self.env.observation_space.subtype, CompleteObservation)
        assert self.env.observation_space.n == 420


class TestEDUC_CASE14_REDISP(unittest.TestCase):
    def setUp(self) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.env = grid2op.make("educ_case14_redisp", test=True)

    def test_elements(self):
        assert self.env.n_sub == 14
        assert self.env.n_line == 20
        assert self.env.n_load == 11
        assert self.env.n_gen == 6
        assert self.env.n_storage == 0

    def test_opponent(self):
        assert issubclass(self.env._opponent_action_class, DontAct)
        assert self.env._opponent_action_space.n == 0

    def test_action_space(self):
        assert issubclass(self.env.action_space.subtype, PlayableAction)
        assert self.env.action_space.n == 26

    def test_observation_space(self):
        assert issubclass(self.env.observation_space.subtype, CompleteObservation)
        assert self.env.observation_space.n == 420


class TestEDUC_CASE14_STORAGE(unittest.TestCase):
    def setUp(self) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.env = grid2op.make("educ_case14_storage", test=True)

    def test_elements(self):
        assert self.env.n_sub == 14
        assert self.env.n_line == 20
        assert self.env.n_load == 11
        assert self.env.n_gen == 6
        assert self.env.n_storage == 2

    def test_opponent(self):
        assert issubclass(self.env._opponent_action_class, DontAct)
        assert self.env._opponent_action_space.n == 0

    def test_action_space(self):
        assert issubclass(self.env.action_space.subtype, PlayableAction)
        assert self.env.action_space.n == 28

    def test_observation_space(self):
        assert issubclass(self.env.observation_space.subtype, CompleteObservation)
        assert self.env.observation_space.n == 428


if __name__ == "__main__":
    unittest.main()
