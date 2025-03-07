# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Grid2Op, Grid2Op a testbed platform to model sequential decision making in power systems.

import copy
import numpy as np
import warnings

from grid2op.dtypes import dt_int, dt_bool, dt_float
from grid2op.Exceptions import *
from grid2op.Space import GridObjects

# TODO time delay somewhere (eg action is implemented after xxx timestep, and not at the time where it's proposed)

# TODO have the "reverse" action, that does the opposite of an action. Will be hard but who know ? :eyes:
# TODO ie:  action + (rev_action) = do_nothing_action

# TODO consistency in names gen_p / prod_p and in general gen_* prod_*


class BaseAction(GridObjects):
    """
    This is a base class for each :class:`BaseAction` objects.
    As stated above, an action represents conveniently the modifications that will affect a powergrid.

    It is not recommended to instantiate an action from scratch. The recommended way to get an action is either by
    modifying an existing one using the method :func:`BaseAction.update` or to call and :class:`ActionSpace` object that
    has been properly set up by an :class:`grid2op.Environment`.

    BaseAction can be fully converted to and back from a numpy array with a **fixed** size.

    An action can modify the grid in multiple ways.
    It can change :

    - the production and voltage setpoint of the generator units
    - the amount of power consumed (for both active and reactive part) for load
    - disconnect powerlines
    - change the topology of the _grid.

    To be valid, an action should be convertible to a tuple of 5 elements:

    - the first element is the "injections" vector: representing the way generator units and loads are modified

        - It is, in turn, a dictionary with the following keys (optional)

            - "load_p" a vector of the same size of the load, giving the modification of the loads active consumption
            - "load_q" a vector of the same size of the load, giving the modification of the loads reactive consumption
            - "prod_p" a vector of the same size of the generators, giving the modification of the productions active
              setpoint production
            - "prod_v" a vector of the same size of the generators, giving the modification of the productions voltage
              setpoint

    - the second element is made of force line status. It is made of a vector of size :attr:`BaseAction._n_lines`
      (the number of lines in the powergrid) and is interpreted as:

            - -1 force line disconnection
            - +1 force line reconnection
            - 0 do nothing to this line

    - the third element is the switch line status vector. It is made of a vector of size :attr:`BaseAction.n_line`
      and is
      interpreted as:

        - ``True``: change the line status
        - ``False``: don't do anything

    - the fourth element set the buses to which the object is connected. It's a vector of integers with the following
      interpretation:

        - 0 -> don't change
        - 1 -> connect to bus 1
        - 2 -> connect to bus 2
        - -1 -> disconnect the object.

    - the fifth element changes the buses to which the object is connected. It's a boolean vector interpreted as:

        - ``False``: nothing is done
        - ``True``: change the bus eg connect it to bus 1 if it was connected to bus 2 or connect it to bus 2 if it was
          connected to bus 1. NB this is only active if the system has only 2 buses per substation (that's the case for
          the L2RPN challenge).

    - the sixth element is a vector, representing the redispatching. Component of this vector is added to the
      generators active setpoint value (if set) of the first elements.

    **NB** the difference between :attr:`BaseAction._set_topo_vect` and :attr:`BaseAction._change_bus_vect` is the
    following:

        - If  a component of :attr:`BaseAction._set_topo_vect` is 1, then the object (load, generator or powerline)
          will be moved to bus 1 of the substation to which it is connected. If it is already to bus 1 nothing will be
          done.
          If it's on another bus it will connect it to bus 1. It's disconnected, it will reconnect it and connect it
          to bus 1.
        - If a component of :attr:`BaseAction._change_bus_vect` is True, then the object will be moved from one bus to
          another.
          If the object were on bus 1
          it will be moved on bus 2, and if it were on bus 2, it will be moved on bus 1. If the object were
          disconnected,
          then this does nothing.

    The conversion to the action into an understandable format by the backend is performed by the "update" method,
    that takes into account a dictionary and is responsible to convert it into this format.
    It is possible to overload this class as long as the overloaded :func:`BaseAction.__call__` operator returns the
    specified format, and the :func:`BaseAction.__init__` method has the same signature.

    This format is then digested by the backend and the powergrid is modified accordingly.

    Attributes
    ----------

    _set_line_status: :class:`numpy.ndarray`, dtype:int
        For each powerline, it gives the effect of the action on the status of it. It should be understood as:

          - -1: disconnect the powerline
          - 0: don't affect the powerline
          - +1: reconnect the powerline

    _switch_line_status: :class:`numpy.ndarray`, dtype:bool
        For each powerline, it informs whether the action will switch the status of a powerline of not. It should be
        understood as followed:

          - ``False``: the action doesn't affect the powerline
          - ``True``: the action affects the powerline. If it was connected, it will disconnect it. If it was
            disconnected, it will reconnect it.

    _dict_inj: ``dict``
        Represents the modification of the injection (productions and loads) of the power _grid. This dictionary can
        have the optional keys:

            - "load_p" to set the active load values (this is a numpy array with the same size as the number of load
              in the power _grid with Nan: don't change anything, else set the value
            - "load_q": same as above but for the load reactive values
            - "prod_p": same as above but for the generator active setpoint values. It has the size corresponding
              to the number of generators in the test case.
            - "prod_v": same as above but set the voltage setpoint of generator units.

    _set_topo_vect: :class:`numpy.ndarray`, dtype:int
        Similar to :attr:`BaseAction._set_line_status` but instead of affecting the status of powerlines, it affects the
        bus connectivity at a substation. It has the same size as the full topological vector
        (:attr:`BaseAction._dim_topo`)
        and for each element it should be understood as:

            - 0 -> don't change
            - 1 -> connect to bus 1
            - 2 -> connect to bus 2
            - -1 -> disconnect the object.

    _change_bus_vect: :class:`numpy.ndarray`, dtype:bool
         Similar to :attr:`BaseAction._switch_line_status` but it affects the topology at substations instead of the
         status of
         the powerline. It has the same size as the full topological vector (:attr:`BaseAction._dim_topo`) and each
         component should mean:

             - ``False``: the object is not affected
             - ``True``: the object will be moved to another bus. If it was on bus 1 it will be moved on bus 2, and if
               it was on bus 2 it will be moved on bus 1.

    authorized_keys: :class:`set`
        The set indicating which keys the actions can understand when calling :func:`BaseAction.update`

    _subs_impacted: :class:`numpy.ndarray`, dtype:bool
        This attributes is either not initialized (set to ``None``) or it tells, for each substation, if it is impacted
        by the action (in this case :attr:`BaseAction._subs_impacted`\[sub_id\] is ``True``) or not
        (in this case :attr:`BaseAction._subs_impacted`\[sub_id\] is ``False``)

    _lines_impacted: :class:`numpy.ndarray`, dtype:bool
        This attributes is either not initialized (set to ``None``) or it tells, for each powerline, if it is impacted
        by the action (in this case :attr:`BaseAction._lines_impacted`\[line_id\] is ``True``) or not
        (in this case :attr:`BaseAction._subs_impacted`\[line_id\] is ``False``)

    attr_list_vect: ``list``, static
        The authorized key that are processed by :func:`BaseAction.__call__` to modify the injections

    attr_list_vect_set: ``set``, static
        The authorized key that is processed by :func:`BaseAction.__call__` to modify the injections

    _redispatch: :class:`numpy.ndarray`, dtype:float
        Amount of redispatching that this action will perform. Redispatching will increase the generator's active
        setpoint
        value. This will be added to the value of the generators. The Environment will make sure that every physical
        constraint is met. This means that the agent provides a setpoint, but there is no guarantee that the setpoint
        will be achievable. Redispatching action is cumulative, this means that if at a given timestep you ask +10 MW
        on a generator, and on another you ask +10 MW then the total setpoint for this generator that the environment
        will try to implement is +20MW.

    _storage_power: :class:`numpy.ndarray`, dtype:float
        Amount of power you want each storage units to produce / absorbs. Storage units are in "loads"
        convention. This means that if you ask for a positive number, the storage unit will absorb
        power from the grid (=it will charge) and if you ask for a negative number, the storage unit
        will inject power on the grid (storage unit will discharge).

    Examples
    --------
    Here are example on how to use the action, for more information on what will be the effect of each,
    please refer to the explanatory notebooks.

    You have two main methods to build actions, as showed here:

    .. code-block:: python

        import grid2op
        env_name = ...
        env = grid2op.make(env_name)

        # first method:
        action_description = {...}  # see below
        act = env.action_space(action_description)

        # second method
        act = env.action_space()
        act.PROPERTY = MODIF

    The description of action as a dictionary is the "historical" method. The method using the properties
    has been added to simplify the API.

    To connect / disconnect powerline, using the "set" action, you can:

    .. code-block:: python

        # method 1
        act = env.action_space({"set_line_status": [(line_id, new_status), (line_id, new_status), ...]})

        # method 2
        act = env.action_space()
        act.line_set_status = [(line_id, new_status), (line_id, new_status), ...]

    typically: 0 <= line_id <= env.n_line and new_status = 1 or -1

    To connect / disconnect powerline using the "change" action type, you can:

    .. code-block:: python

        # method 1
        act = env.action_space({"change_line_status": [line_id, line_id, ...]})

        # method 2
        act = env.action_space()
        act.line_change_status = [line_id, line_id, ...]

    typically: 0 <= line_id <= env.n_line

    To modify the busbar at which an element is connected you can (if using set, to use "change" instead
    replace "set_bus" in the text below by "change_bus" **eg** `nv.action_space({"change_bus": ...})`
    or `act.load_change_bus = ...` ):

    .. code-block:: python

        # method 1
        act = env.action_space({"set_bus":
                                    {"lines_or_id": [(line_id, new_bus), (line_id, new_bus), ...],
                                     "lines_ex_id": [(line_id, new_bus), (line_id, new_bus), ...],
                                     "loads_id": [(load_id, new_bus), (load_id, new_bus), ...],
                                     "generators_id": [(gen_id, new_bus), (gen_id, new_bus), ...],
                                     "storages_id": [(storage_id, new_bus), (storage_id, new_bus), ...]
                                     }
                                })

        # method 2
        act = env.action_space()
        act.line_or_set_bus = [(line_id, new_bus), (line_id, new_bus), ...]
        act.line_ex_set_bus = [(line_id, new_bus), (line_id, new_bus), ...]
        act.load_set_bus =  [(load_id, new_bus), (load_id, new_bus), ...]
        act.gen_set_bus = [(gen_id, new_bus), (gen_id, new_bus), ...]
        act.storage_set_bus = [(storage_id, new_bus), (storage_id, new_bus), ...]

    Of course you can modify one type of object at a time (you don't have to specify all "lines_or_id",
    "lines_ex_id", "loads_id", "generators_id", "storages_id"

    You can also give the topologies you want at each substations with:

    .. code-block:: python

        # method 1
        act = env.action_space({"set_bus":{
                                "substations_id": [(sub_id, topo_sub), (sub_id, topo_sub), ...]
                                }})
        # method 2
        act = env.action_space()
        act.sub_set_bus = [(sub_id, topo_sub), (sub_id, topo_sub), ...]

    In the above typically 0 <= sub_id < env.n_sub and topo_sub is a vector having the right dimension (
    so if a substation has 4 elements, then topo_sub should have 4 elements)

    It has to be noted that `act.sub_set_bus` will return a 1d vector representing the topology
    of the grid as "set" by the action, with the convention, -1 => disconnect, 0 => don't change,
    1=> set to bus 1 and 2 => set object to bus 2.


    In order to perform redispatching you can do as follow:

    .. code-block:: python

        # method 1
        act = env.action_space({"redispatch": [(gen_id, amount), (gen_id, amount), ...]})
        # method 2
        act = env.action_space()
        act.redispatch = [(gen_id, amount), (gen_id, amount), ...]

    Typically 0<= gen_id < env.n_gen and `amount` is a floating point between gen_max_ramp_down and
    gen_min_ramp_down for the generator modified.

    Finally, in order to perform action on storage units, you can:

    .. code-block:: python

        # method 1
        act = env.action_space({"set_storage": [(storage_id, amount), (storage_id, amount), ...]})

        # method 2
        act = env.action_space()
        act.storage_p = [(storage_id, amount), (storage_id, amount), ...]

    Typically `0 <= storage_id < env.n_storage` and `amount` is a floating point between the maximum
    power and minimum power the storage unit can absorb / produce.

    """
    authorized_keys = {"injection",
                       "hazards", "maintenance", "set_line_status", "change_line_status",
                       "set_bus", "change_bus", "redispatch", "set_storage"}

    attr_list_vect = ["prod_p", "prod_v", "load_p", "load_q", "_redispatch",
                      "_set_line_status", "_switch_line_status",
                      "_set_topo_vect", "_change_bus_vect", "_hazards", "_maintenance",
                      "_storage_power"
                      ]
    attr_list_set = set(attr_list_vect)
    shunt_added = False

    _line_or_str = "line (origin)"
    _line_ex_str = "line (extremity)"

    def __init__(self):
        """
        INTERNAL USE ONLY

        .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

            **It is NOT recommended** to create an action with this method, use the action space
            of the environment :attr:`grid2op.Environment.Environment.action_space` instead.

        This is used to create an BaseAction instance. Preferably, :class:`BaseAction` should be created with
        :class:`ActionSpace`.

        IMPORTANT: Use :func:`ActionSpace.__call__` or :func:`ActionSpace.sample` to generate a valid action.

        """
        GridObjects.__init__(self)

        # False(line is disconnected) / True(line is connected)
        self._set_line_status = np.full(shape=self.n_line, fill_value=0, dtype=dt_int)
        self._switch_line_status = np.full(shape=self.n_line, fill_value=False, dtype=dt_bool)

        # injection change
        self._dict_inj = {}

        # topology changed
        self._set_topo_vect = np.full(shape=self.dim_topo, fill_value=0, dtype=dt_int)
        self._change_bus_vect = np.full(shape=self.dim_topo, fill_value=False, dtype=dt_bool)

        # add the hazards and maintenance usefull for saving.
        self._hazards = np.full(shape=self.n_line, fill_value=False, dtype=dt_bool)
        self._maintenance = np.full(shape=self.n_line, fill_value=False, dtype=dt_bool)

        # redispatching vector
        self._redispatch = np.full(shape=self.n_gen, fill_value=0., dtype=dt_float)

        # storage unit vector
        self._storage_power = np.full(shape=self.n_storage, fill_value=0., dtype=dt_float)

        self._vectorized = None
        self._lines_impacted = None
        self._subs_impacted = None

        # shunts
        if self.shunts_data_available:
            self.shunt_p = np.full(shape=self.n_shunt, fill_value=np.NaN, dtype=dt_float)
            self.shunt_q = np.full(shape=self.n_shunt, fill_value=np.NaN, dtype=dt_float)
            self.shunt_bus = np.full(shape=self.n_shunt, fill_value=0, dtype=dt_int)
        else:
            self.shunt_p = None
            self.shunt_q = None
            self.shunt_bus = None

        if BaseAction.shunt_added is False and self.shunts_data_available:
            BaseAction.shunt_added = True
            BaseAction.attr_list_vect += ["shunt_p", "shunt_q", "shunt_bus"]
            BaseAction.authorized_keys.add("shunt")
            BaseAction._update_value_set()

        self._single_act = True

        # change the stuff
        self._modif_inj = False
        self._modif_set_bus = False
        self._modif_change_bus = False
        self._modif_set_status = False
        self._modif_change_status = False
        self._modif_redispatch = False
        self._modif_storage = False

    def _reset_modified_flags(self):
        self._modif_inj = False
        self._modif_set_bus = False
        self._modif_change_bus = False
        self._modif_set_status = False
        self._modif_change_status = False
        self._modif_redispatch = False
        self._modif_storage = False

    def _get_array_from_attr_name(self, attr_name):
        if hasattr(self, attr_name):
            res = super()._get_array_from_attr_name(attr_name)
        else:
            if attr_name in self._dict_inj:
                res = self._dict_inj[attr_name]
            else:
                if attr_name == "prod_p" or attr_name == "prod_v":
                    res = np.full(self.n_gen, fill_value=0., dtype=dt_float)
                elif attr_name == "load_p" or attr_name == "load_q":
                    res = np.full(self.n_load, fill_value=0., dtype=dt_float)
                else:
                    raise Grid2OpException("Impossible to find the attribute \"{}\" "
                                           "into the BaseAction of type \"{}\"".format(attr_name, type(self)))
        return res

    def _post_process_from_vect(self):
        self._modif_inj = self._dict_inj != {}
        self._modif_set_bus = np.any(self._set_topo_vect != 0)
        self._modif_change_bus = np.any(self._change_bus_vect)
        self._modif_set_status = np.any(self._set_line_status != 0)
        self._modif_change_status = np.any(self._switch_line_status)
        self._modif_redispatch = np.any(np.isfinite(self._redispatch) & (self._redispatch != 0.))
        self._modif_storage = np.any(np.isfinite(self._storage_power))

    def _assign_attr_from_name(self, attr_nm, vect):
        if hasattr(self, attr_nm):
            super()._assign_attr_from_name(attr_nm, vect)
        else:
            if np.any(np.isfinite(vect)):
                if np.any(vect != 0.):
                    self._dict_inj[attr_nm] = vect

    def check_space_legit(self):
        """
        This method allows to check if this method is ambiguous **per se** (defined more formally as:
        whatever the observation at time *t*, and the changes that can occur between *t* and *t+1*, this
        action will be ambiguous).

        For example, an action that try to assign something to busbar 3 will be ambiguous *per se*. An action
        that tries to dispatch a non dispatchable generator will be also ambiguous *per se*.

        However, an action that "switch" (change) the status (connected / disconnected) of a powerline can be
        ambiguous and it will not be detected here. This is because the ambiguity depends on the current state
        of the powerline:

        - if the powerline is disconnected, changing its status means reconnecting it. And we cannot reconnect a
          powerline without specifying on which bus.
        - on the contrary if the powerline is connected, changing its status means disconnecting it, which is
          always feasible.

        In case of "switch" as we see here, the action can be ambiguous, but not ambiguous *per se*. This method
        will **never** throw any error in this case.

        Raises
        -------
        :class:`grid2op.Exceptions.AmbiguousAction`
            Or any of its more precise subclasses, depending on which assumption is not met.

        """
        self._check_for_ambiguity()

    def get_set_line_status_vect(self):
        """
        Computes and returns a vector that can be used in the :func:`BaseAction.__call__` with the keyword
        "set_status" if building an :class:`BaseAction`.

        **NB** this vector is not the internal vector of this action but corresponds to "do nothing" action.

        Returns
        -------
        res: :class:`numpy.array`, dtype:dt_int
            A vector that doesn't affect the grid, but can be used in :func:`BaseAction.__call__` with the keyword
            "set_status" if building an :class:`BaseAction`.

        """
        return np.full(shape=self.n_line, fill_value=0, dtype=dt_int)

    def get_change_line_status_vect(self):
        """
        Computes and returns a vector that can be used in the :func:`BaseAction.__call__` with the keyword
        "set_status" if building an :class:`BaseAction`.

        **NB** this vector is not the internal vector of this action but corresponds to "do nothing" action.

        Returns
        -------
        res: :class:`numpy.array`, dtype:dt_bool
            A vector that doesn't affect the grid, but can be used in :func:`BaseAction.__call__` with the keyword
            "set_status" if building an :class:`BaseAction`.

        """
        return np.full(shape=self.n_line, fill_value=False, dtype=dt_bool)

    def __eq__(self, other) -> bool:
        """
        Test the equality of two actions.

        2 actions are said to be identical if they have the same impact on the powergrid. This is unrelated to their
        respective class. For example, if an Action is of class :class:`Action` and doesn't act on the injection, it
        can be equal to an Action of the derived class :class:`TopologyAction` (if the topological modifications are the
        same of course).

        This implies that the attributes :attr:`Action.authorized_keys` is not checked in this method.

        Note that if 2 actions don't act on the same powergrid, or on the same backend (eg number of loads, or
        generators are not the same in *self* and *other*, or they are not in the same order) then action will be
        declared as different.

        **Known issue** if two backends are different, but the description of the _grid are identical (ie all
        n_gen, n_load, n_line, sub_info, dim_topo, all vectors \*_to_subid, and \*_pos_topo_vect are
        identical) then this method will not detect the backend are different, and the action could be declared
        as identical. For now, this is only a theoretical behavior: if everything is the same, then probably, up to
        the naming convention, then the power grids are identical too.

        Parameters
        ----------
        other: :class:`BaseAction`
            An instance of class Action to which "self" will be compared.

        Returns
        -------
        res: ``bool``
            Whether the actions are equal or not.

        """
        if other is None:
            return False

        # check that the underlying grid is the same in both instances
        same_grid = type(self).same_grid_class(type(other))
        if not same_grid:
            return False

        # _grid is the same, now I test the the injections modifications are the same
        same_action = self._modif_inj == other._modif_inj
        same_action = same_action and self._dict_inj.keys() == other._dict_inj.keys()
        if not same_action:
            return False

        # all injections are the same
        for el in self._dict_inj.keys():
            me_inj = self._dict_inj[el]
            other_inj = other._dict_inj[el]
            tmp_me = np.isfinite(me_inj)
            tmp_other = np.isfinite(other_inj)
            if not np.all(tmp_me == tmp_other) or \
                    not np.all(me_inj[tmp_me] == other_inj[tmp_other]):
                return False

        # same line status
        if (self._modif_set_status != other._modif_set_status) or \
                not np.all(self._set_line_status == other._set_line_status):
            return False

        if (self._modif_change_status != other._modif_change_status) or \
            not np.all(self._switch_line_status == other._switch_line_status):
            return False

        # redispatching is same
        if (self._modif_redispatch != other._modif_redispatch) or \
                not np.all(self._redispatch == other._redispatch):
            return False

        # storage is same
        me_inj = self._storage_power
        other_inj = other._storage_power
        tmp_me = np.isfinite(me_inj)
        tmp_other = np.isfinite(other_inj)
        if not np.all(tmp_me == tmp_other) or \
                not np.all(me_inj[tmp_me] == other_inj[tmp_other]):
            return False

        # same topology changes
        if (self._modif_set_bus != other._modif_set_bus) or \
                not np.all(self._set_topo_vect == other._set_topo_vect):
            return False
        if (self._modif_change_bus != other._modif_change_bus) or \
                not np.all(self._change_bus_vect == other._change_bus_vect):
            return False

        # shunts are the same
        if self.shunts_data_available:
            if self.n_shunt != other.n_shunt:
                return False
            is_ok_me = np.isfinite(self.shunt_p)
            is_ok_ot = np.isfinite(other.shunt_p)
            if np.any(is_ok_me != is_ok_ot):
                return False
            if not np.all(self.shunt_p[is_ok_me] == other.shunt_p[is_ok_ot]):
                return False
            is_ok_me = np.isfinite(self.shunt_q)
            is_ok_ot = np.isfinite(other.shunt_q)
            if np.any(is_ok_me != is_ok_ot):
                return False
            if not np.all(self.shunt_q[is_ok_me] == other.shunt_q[is_ok_ot]):
                return False
            if not np.all(self.shunt_bus == other.shunt_bus):
                return False

        return True

    def get_topological_impact(self, powerline_status=None):
        """
        Gives information about the element being impacted by this action.
        **NB** The impacted elements can be used by :class:`grid2op.BaseRules` to determine whether or not an action
        is legal or not.
        **NB** The impacted are the elements that can potentially be impacted by the action. This does not mean they
        will be impacted. For examples:

        * If an action from an :class:`grid2op.BaseAgent` reconnect a powerline, but this powerline is being
          disconnected by a hazard at the same time step, then this action will not be implemented on the grid.

        However, it this powerline couldn't be reconnected for some reason (for example it was already out of order)
        the action will still be declared illegal, even if it has NOT impacted the powergrid.

        * If an action tries to disconnect a powerline already disconnected, it will "impact" this powergrid.
          This means that even if the action will do nothing, it disconnecting this powerline is against the rules,
          then the action will be illegal.
        * If an action tries to change the topology of a substation, but this substation is already at the target
          topology, the same mechanism applies. The action will "impact" the substation, even if, in the end, it
          consists of doing nothing.

        Any such "change" that would be illegal is declared as "illegal" regardless of the real impact of this action
        on the powergrid.

        Returns
        -------
        lines_impacted: :class:`numpy.array`, dtype:dt_bool
            A vector with the same size as the number of powerlines in the grid (:attr:`BaseAction.n_line`) with for
            each component ``True`` if the line STATUS is impacted by the action, and ``False`` otherwise. See
            :attr:`BaseAction._lines_impacted` for more information.

        subs_impacted: :class:`numpy.array`, dtype:dt_bool
            A vector with the same size as the number of substations in the grid with for each
            component ``True`` if the substation is impacted by the action, and ``False`` otherwise. See
            :attr:`BaseAction._subs_impacted` for more information.

        """
        if powerline_status is None:
            isnotconnected = np.full(self.n_line, fill_value=True, dtype=dt_bool)
        else:
            isnotconnected = ~powerline_status

        self._lines_impacted = self._switch_line_status | (self._set_line_status != 0)
        self._subs_impacted = np.full(shape=self.sub_info.shape, fill_value=False, dtype=dt_bool)

        # compute the changes of the topo vector
        effective_change = self._change_bus_vect | (self._set_topo_vect != 0)

        # remove the change due to powerline only
        effective_change[self.line_or_pos_topo_vect[self._lines_impacted & isnotconnected]] = False
        effective_change[self.line_ex_pos_topo_vect[self._lines_impacted & isnotconnected]] = False

        # i can change also the status of a powerline by acting on its extremity
        # first sub case i connected the powerline by setting origin OR extremity to positive stuff
        if powerline_status is not None:
            # if we don't know the state of the grid, we don't consider
            # these "improvments": we consider a powerline is never
            # affected if its bus is modified at any of its ends.
            connect_set_or = (self._set_topo_vect[self.line_or_pos_topo_vect] > 0) & (isnotconnected)
            self._lines_impacted |= connect_set_or
            effective_change[self.line_or_pos_topo_vect[connect_set_or]] = False
            effective_change[self.line_ex_pos_topo_vect[connect_set_or]] = False
            connect_set_ex = (self._set_topo_vect[self.line_ex_pos_topo_vect] > 0) & (isnotconnected)
            self._lines_impacted |= connect_set_ex
            effective_change[self.line_or_pos_topo_vect[connect_set_ex]] = False
            effective_change[self.line_ex_pos_topo_vect[connect_set_ex]] = False

            # second sub case i disconnected the powerline by setting origin or extremity to negative stuff
            disco_set_or = (self._set_topo_vect[self.line_or_pos_topo_vect] < 0) & (~isnotconnected)
            self._lines_impacted |= disco_set_or
            effective_change[self.line_or_pos_topo_vect[disco_set_or]] = False
            effective_change[self.line_ex_pos_topo_vect[disco_set_or]] = False
            disco_set_ex = (self._set_topo_vect[self.line_ex_pos_topo_vect] < 0) & (~isnotconnected)
            self._lines_impacted |= disco_set_ex
            effective_change[self.line_or_pos_topo_vect[disco_set_ex]] = False
            effective_change[self.line_ex_pos_topo_vect[disco_set_ex]] = False

        self._subs_impacted[self._topo_vect_to_sub[effective_change]] = True
        return self._lines_impacted, self._subs_impacted

    def reset(self):
        """
        INTERNAL USE ONLY

        .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

        Reset the action to the "do nothing" state.

        """
        # False(line is disconnected) / True(line is connected)
        self._set_line_status[:] = 0
        self._switch_line_status[:] = False

        # injection change
        self._dict_inj = {}

        # topology changed
        self._set_topo_vect[:] = 0
        self._change_bus_vect[:] = False

        # add the hazards and maintenance usefull for saving.
        self._hazards[:] = False
        self._maintenance[:] = False

        # redispatching vector
        self._redispatch[:] = 0.

        # storage
        self._storage_power[:] = 0.

        self._vectorized = None
        self._lines_impacted = None
        self._subs_impacted = None

        # shunts
        if self.shunts_data_available:
            self.shunt_p[:] = np.NaN
            self.shunt_q[:] = np.NaN
            self.shunt_bus[:] = 0

        self._reset_modified_flags()

    def _assign_iadd_or_warn(self, attr_name, new_value):
        if attr_name not in self.attr_list_set:
            old_value = getattr(self, attr_name)
            new_is_finite = np.isfinite(new_value)
            old_is_finite = np.isfinite(old_value)
            new_finite = new_value[new_is_finite | old_is_finite]
            old_finite = old_value[new_is_finite | old_is_finite]
            if np.any(new_finite != old_finite):
                warnings.warn("The action added to me will be cut, because i don't support modification of \"{}\""
                              "".format(attr_name))
        else:
            getattr(self, attr_name)[:] = new_value

    def __iadd__(self, other):
        """
        Add an action to this one.

        Adding an action to myself is equivalent to perform myself, and then perform other (but at the
        same step)

        Parameters
        ----------
        other: :class:`BaseAction`

        Examples
        --------

        .. code-block:: python

            import grid2op
            env_name = ...
            env = grid2op.make(env_name)

            act1 = env.action_space()
            act1.set_bus = ...  # for example
            print("before += :")
            print(act1)

            act2 = env.action_space()
            act2.redispatch = ... # for example
            print(act2)

            act1 += act 2
            print("after += ")
            print(act1)

        """

        # deal with injections
        for el in self.attr_list_vect:
            if el in other._dict_inj:
                if el not in self._dict_inj:
                    self._dict_inj[el] = other._dict_inj[el]
                else:
                    val = other._dict_inj[el]
                    ok_ind = np.isfinite(val)
                    self._dict_inj[el][ok_ind] = val[ok_ind]
        # warning if the action cannot be added
        for el in other._dict_inj:
            if not el in self.attr_list_set:
                warnings.warn("The action added to me will be cut, because i don't support modification of \"{}\""
                              "".format(el))
        # redispatching
        redispatching = other._redispatch
        if np.any(redispatching != 0.):
            if "_redispatch" not in self.attr_list_set:
                warnings.warn("The action added to me will be cut, because i don't support modification of \"{}\""
                              "".format("_redispatch"))
            else:
                ok_ind = np.isfinite(redispatching)
                self._redispatch[ok_ind] += redispatching[ok_ind]

        # storage
        set_storage = other._storage_power
        ok_ind = np.isfinite(set_storage) & np.any(set_storage != 0.)
        if np.any(ok_ind):
            if "_storage_power" not in self.attr_list_set:
                warnings.warn("The action added to me will be cut, because i don't support modification of \"{}\""
                              "".format("_storage_power"))
            else:
                self._storage_power[ok_ind] += set_storage[ok_ind]

        # set and change status
        other_set = other._set_line_status
        other_change = other._switch_line_status
        me_set = 1 * self._set_line_status
        me_change = copy.deepcopy(self._switch_line_status)

        # i change, but so does the other, i do nothing
        canceled_change = other_change & me_change
        # i dont change, the other change, i change
        update_change = other_change & ~me_change
        # Defered apply to prevent conflicts
        me_change[canceled_change] = False
        me_change[update_change] = True

        # i change, but the other set, it's erased
        me_change[other_set != 0 & me_change] = False

        # i set, but the other change, set to the opposite
        inverted_set = other_change & (me_set != 0)
        # so change +1 becomes -1 and -1 becomes +1
        me_set[inverted_set] *= -1
        # Has been inverted, cancel change
        me_change[inverted_set] = False

        # i set, the other set
        me_set[other_set != 0] = other_set[other_set != 0]

        self._assign_iadd_or_warn("_set_line_status", me_set)
        self._assign_iadd_or_warn("_switch_line_status", me_change)

        # set and change bus
        other_set = other._set_topo_vect
        other_change = other._change_bus_vect
        me_set = 1 * self._set_topo_vect
        me_change = copy.deepcopy(self._change_bus_vect)

        # i change, but so does the other, i do nothing
        canceled_change = other_change & me_change
        # i dont change, the other change, i change
        update_change = other_change & ~me_change
        # Defered apply to prevent conflicts
        me_change[canceled_change] = False
        me_change[update_change] = True

        # i change, but the other set, it's erased
        me_change[other_set != 0 & me_change] = False

        # i set, but the other change, set to the opposite
        inverted_set = other_change & (me_set != 0)
        # so change +1 becomes +2 and +2 becomes +1
        me_set[inverted_set] -= 1  # 1 becomes 0 and 2 becomes 1
        me_set[inverted_set] *= -1  # 1 is 0 and 2 becomes -1
        me_set[inverted_set] += 2  # 1 is 2 and 2 becomes 1
        # Has been inverted, cancel change
        me_change[inverted_set] = False

        # i set, the other set
        me_set[other_set != 0] = other_set[other_set != 0]
        
        self._assign_iadd_or_warn("_set_topo_vect", me_set)
        self._assign_iadd_or_warn("_change_bus_vect", me_change)

        # shunts
        if self.shunts_data_available:
            val = other.shunt_p
            ok_ind = np.isfinite(val)
            shunt_p = 1.0 * self.shunt_p
            shunt_p[ok_ind] = val[ok_ind]
            self._assign_iadd_or_warn("shunt_p", shunt_p)

            val = other.shunt_q
            ok_ind = np.isfinite(val)
            shunt_q = 1.0 * self.shunt_q
            shunt_q[ok_ind] = val[ok_ind]
            self._assign_iadd_or_warn("shunt_q", shunt_q)

            val = other.shunt_bus
            ok_ind = val != 0
            shunt_bus = 1 * self.shunt_bus
            shunt_bus[ok_ind] = val[ok_ind]
            self._assign_iadd_or_warn("shunt_bus", shunt_bus)

        self._modif_change_bus = self._modif_change_bus or other._modif_change_bus
        self._modif_set_bus = self._modif_set_bus or other._modif_set_bus
        self._modif_change_status = self._modif_change_status or other._modif_change_status
        self._modif_set_status = self._modif_set_status or other._modif_set_status
        self._modif_inj = self._modif_inj or other._modif_inj
        self._modif_redispatch = self._modif_redispatch or other._modif_redispatch
        self._modif_storage = self._modif_storage or other._modif_storage

        return self

    def __add__(self, other):
        """
        Implements the `+` operator for the action using the `+=` definition.

        This function is not commutative !

        Notes
        -------
        Be careful if two actions do not share the same type (for example you want to add act1
        of type :class:`TopologyAction` to act2 of type :class:`DispatchAction`) the results of
        `act1 + act2` might differ from what you expect.

        The result will always of the same type as act1. In the above case, it means that the `dispatch`
        part of `act2`will be ignored (because it is ignored in :class:`TopologyAction`).

        This is why we recommend to using this class directly with the :class:`PlayableAction` or
        from action directly generated with `env.action_space()`
        """
        res = type(self)()
        res += self
        res += other
        return res

    def __call__(self):
        """
        INTERNAL USE ONLY

         .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

        This method is used to return the effect of the current action in a format understandable by the backend.
        This format is detailed below.

        This function must also integrate the redispatching strategy for the BaseAction.

        It also performs a check of whether or not an action is "Ambiguous", eg an action that reconnect a powerline
        but doesn't specify on which bus to reconnect it is said to be ambiguous.

        If this :func:`BaseAction.__call__` is overloaded, the call of :func:`BaseAction._check_for_ambiguity` must be
        ensured by this the derived class.

        Returns
        -------
        dict_injection: :class:`dict`
            This dictionnary is :attr:`BaseAction._dict_inj`

        set_line_status: :class:`numpy.array`, dtype:int
            This array is :attr:`BaseAction._set_line_status`

        switch_line_status: :class:`numpy.array`, dtype:bool
            This array is :attr:`BaseAction._switch_line_status`

        set_topo_vect: :class:`numpy.array`, dtype:int
            This array is :attr:`BaseAction._set_topo_vect`

        change_bus_vect: :class:`numpy.array`, dtype:bool
            This array is :attr:`BaseAction._change_bus_vect`

        redispatch: :class:`numpy.ndarray`, dtype:float
            This array, that has the same size as the number of generators indicates for each generator the amount of
            redispatching performed by the action.

        storage_power: :class:`numpy.ndarray`, dtype:float
            Indicates, for all storage units, what is the production / absorbtion setpoint

        shunts: ``dict``
            A dictionnary containing the shunts data, with keys: "shunt_p", "shunt_q" and "shunt_bus" and the
            convention, for "shun_p" and "shunt_q" that Nan means "don't change" and for shunt_bus: -1 => disconnect
            0 don't change, and 1 / 2 connect to bus 1 / 2

        Raises
        -------
        :class:`grid2op.Exceptions.AmbiguousAction`
            Or one of its derivate class.

        """

        self._check_for_ambiguity()

        dict_inj = self._dict_inj
        set_line_status = self._set_line_status
        switch_line_status = self._switch_line_status
        set_topo_vect = self._set_topo_vect
        change_bus_vect = self._change_bus_vect
        redispatch = self._redispatch
        storage_power = self._storage_power
        shunts = {}
        if self.shunts_data_available:
            shunts["shunt_p"] = self.shunt_p
            shunts["shunt_q"] = self.shunt_q
            shunts["shunt_bus"] = self.shunt_bus
        return dict_inj, \
               set_line_status, switch_line_status, \
               set_topo_vect, change_bus_vect, \
               redispatch, storage_power, \
               shunts

    def _digest_shunt(self, dict_):
        if not self.shunts_data_available:
            return
        if "shunt" in dict_:
            ddict_ = dict_["shunt"]

            key_shunt_reco = {"set_bus", "shunt_p", "shunt_q", "shunt_bus"}
            for k in ddict_:
                if k not in key_shunt_reco:
                    warn = "The key {} is not recognized by BaseAction when trying to modify the shunt.".format(k)
                    warn += " Recognized keys are {}".format(sorted(key_shunt_reco))
                    warnings.warn(warn)

            for key_n, vect_self in zip(["shunt_bus", "shunt_p", "shunt_q", "set_bus"],
                                        [self.shunt_bus, self.shunt_p, self.shunt_q, self.shunt_bus]):
                if key_n in ddict_:
                    tmp = ddict_[key_n]
                    if isinstance(tmp, np.ndarray):
                        # complete shunt vector is provided
                        vect_self[:] = tmp
                    elif isinstance(tmp, list):
                        # expected a list: (id shunt, new bus)
                        for (sh_id, new_bus) in tmp:
                            if sh_id < 0:
                                raise AmbiguousAction("Invalid shunt id {}. Shunt id should be positive".format(sh_id))
                            if sh_id >= self.n_shunt:
                                raise AmbiguousAction("Invalid shunt id {}. Shunt id should be less than the number "
                                                      "of shunt {}".format(sh_id, self.n_shunt))
                            vect_self[sh_id] = new_bus

                    elif tmp is None:
                        pass
                    else:
                        raise AmbiguousAction("Invalid way to modify {} for shunts. It should be a numpy array or a "
                                               "dictionnary.".format(key_n))

    def _digest_injection(self, dict_):
        # I update the action
        if "injection" in dict_:
            if dict_["injection"] is not None:
                tmp_d = dict_["injection"]
                self._modif_inj = True
                for k in tmp_d:
                    if k in self.attr_list_set:
                        self._dict_inj[k] = np.array(tmp_d[k]).astype(dt_float)
                    else:
                        warn = "The key {} is not recognized by BaseAction when trying to modify the injections." \
                               "".format(k)
                        warnings.warn(warn)

    def _digest_setbus(self, dict_):
        if "set_bus" in dict_:
            self._modif_set_bus = True
            if dict_["set_bus"] is None:
                # no real action has been made
                return

            if isinstance(dict_["set_bus"], dict):
                ddict_ = dict_["set_bus"]
                handled = False
                if "loads_id" in ddict_:
                    self.load_set_bus = ddict_["loads_id"]
                    handled = True
                if "generators_id" in ddict_:
                    self.gen_set_bus = ddict_["generators_id"]
                    handled = True
                if "lines_or_id" in ddict_:
                    self.line_or_set_bus = ddict_["lines_or_id"]
                    handled = True
                if "lines_ex_id" in ddict_:
                    self.line_ex_set_bus = ddict_["lines_ex_id"]
                    handled = True
                if "storages_id" in ddict_:
                    self.storage_set_bus = ddict_["storages_id"]
                    handled = True
                if "substations_id" in ddict_:
                    self.sub_set_bus = ddict_["substations_id"]
                    handled = True
                if not handled:
                    msg = "Invalid way to set the topology. When dict_[\"set_bus\"] is a dictionary it should have"
                    msg += " at least one of \"loads_id\", \"generators_id\", \"lines_or_id\", "
                    msg += "\"lines_ex_id\" or \"substations_id\""
                    msg += " as keys. None where found. Current used keys are: "
                    msg += "{}".format(sorted(ddict_.keys()))
                    raise AmbiguousAction(msg)
            else:
                self.set_bus = dict_["set_bus"]

    def _digest_change_bus(self, dict_):
        if "change_bus" in dict_:
            self._modif_change_bus = True
            if dict_["change_bus"] is None:
                # no real action has been made
                return

            if isinstance(dict_["change_bus"], dict):
                ddict_ = dict_["change_bus"]
                handled = False
                if "loads_id" in ddict_:
                    self.load_change_bus = ddict_["loads_id"]
                    handled = True
                if "generators_id" in ddict_:
                    self.gen_change_bus = ddict_["generators_id"]
                    handled = True
                if "lines_or_id" in ddict_:
                    self.line_or_change_bus = ddict_["lines_or_id"]
                    handled = True
                if "lines_ex_id" in ddict_:
                    self.line_ex_change_bus = ddict_["lines_ex_id"]
                    handled = True
                if "storages_id" in ddict_:
                    self.storage_change_bus = ddict_["storages_id"]
                    handled = True
                if "substations_id" in ddict_:
                    self.sub_change_bus = ddict_["substations_id"]
                    handled = True
                if not handled:
                    msg = "Invalid way to change the topology. When dict_[\"set_bus\"] is a dictionary it should have"
                    msg += " at least one of \"loads_id\", \"generators_id\", \"lines_or_id\", "
                    msg += "\"lines_ex_id\" or \"substations_id\""
                    msg += " as keys. None where found. Current used keys are: "
                    msg += "{}".format(sorted(ddict_.keys()))
                    raise AmbiguousAction(msg)
            else:
                self.change_bus = dict_["change_bus"]

    def _digest_set_status(self, dict_):
        if "set_line_status" in dict_:
            # this action can both disconnect or reconnect a powerlines
            self.line_set_status = dict_["set_line_status"]

    def _digest_hazards(self, dict_):
        if "hazards" in dict_:
            # set the values of the power lines to "disconnected" for element being "False"
            # does nothing to the others
            # an hazard will never reconnect a powerline
            if dict_["hazards"] is not None:
                self._modif_set_status = True
                tmp = dict_["hazards"]
                try:
                    tmp = np.array(tmp)
                except Exception as exc_:
                    raise AmbiguousAction(
                        f"You ask to perform hazard on powerlines, this can only be done if \"hazards\" can be casted "
                        f"into a numpy ndarray with error {exc_}")
                if np.issubdtype(tmp.dtype, np.dtype(bool).type):
                    if len(tmp) != self.n_line:
                        raise InvalidNumberOfLines(
                            "This \"hazards\" action acts on {} lines while there are {} in the _grid".format(
                                len(tmp), self.n_line))
                elif not np.issubdtype(tmp.dtype, np.dtype(int).type):
                    raise AmbiguousAction("You can only ask hazards with int or boolean numpy array vector.")

                self._set_line_status[tmp] = -1
                self._hazards[tmp] = True
                # force ignore of any topological actions
                self._ignore_topo_action_if_disconnection(tmp)

    def _digest_maintenance(self, dict_):
        if "maintenance" in dict_:
            # set the values of the power lines to "disconnected" for element being "False"
            # does nothing to the others
            # a _maintenance operation will never reconnect a powerline
            if dict_["maintenance"] is not None:
                self._modif_set_status = True
                tmp = dict_["maintenance"]
                try:
                    tmp = np.array(tmp)
                except Exception as exc_:
                    raise AmbiguousAction(
                        f"You ask to perform maintenance on powerlines, this can only be done if \"maintenance\" can "
                        f"be casted into a numpy ndarray with error {exc_}")
                if np.issubdtype(tmp.dtype, np.dtype(bool).type):
                    if len(tmp) != self.n_line:
                        raise InvalidNumberOfLines(
                            "This \"maintenance\" action acts on {} lines while there are {} in the _grid".format(
                                len(tmp), self.n_line))
                elif not np.issubdtype(tmp.dtype, np.dtype(int).type):
                    raise AmbiguousAction(
                        "You can only ask to perform lines maintenance with int or boolean numpy array vector.")
                self._set_line_status[tmp] = -1
                self._maintenance[tmp] = True
                self._ignore_topo_action_if_disconnection(tmp)

    def _digest_change_status(self, dict_):
        if "change_line_status" in dict_:
            # the action will switch the status of the powerline
            # for each element equal to 1 in this dict_["change_line_status"]
            # if the status is "disconnected" it will be transformed into "connected"
            # and if the status is "connected" it will be switched to "disconnected"
            # Lines with "0" in this vector are not impacted.
            if dict_["change_line_status"] is not None:
                self.line_change_status = dict_["change_line_status"]

    def _digest_redispatching(self, dict_):
        if "redispatch" in dict_:
            self.redispatch = dict_["redispatch"]

    def _digest_storage(self, dict_):
        if "set_storage" in dict_:
            self.storage_p = dict_["set_storage"]

    def _reset_vect(self):
        """
        INTERNAL USE ONLY

         .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

        Need to be called when update is called !

        """
        self._vectorized = None
        self._subs_impacted = None
        self._lines_impacted = None

    def update(self, dict_):
        """
        Update the action with a comprehensible format specified by a dictionary.

        Preferably, if a key of the argument *dict_* is not found in :attr:`Action.authorized_keys` it should throw a
        warning. This argument will be completely ignored.

        This method also reset the attributes :attr:`Action._vectorized` :attr:`Action._lines_impacted` and
        :attr:`Action._subs_impacted` to ``None`` regardless of the argument in input.

        If an action consists of "reconnecting" a powerline, and this same powerline is affected by maintenance or a
        hazard, it will be erased without any warning. "hazards" and "maintenance" have the priority. This is a
        requirement for all proper :class:`Action` subclass.

        Parameters
        ----------
        dict_: :class:`dict`
            If it's ``None`` or empty it does nothing. Otherwise, it can contain the following (optional) keys:

            - "*injection*" if the action will modify the injections (generator setpoint/load value - active or
              reactive) of the powergrid. It has optionally one of the following keys:

                    - "load_p": to set the active load values (this is a numpy array with the same size as the number of
                      load in the power _grid with Nan: don't change anything, else set the value
                    - "load_q": same as above but for the load reactive values
                    - "prod_p": same as above but for the generator active setpoint values. It has the size
                      corresponding to the number of generators in the test case.
                    - "prod_v": same as above but set the voltage setpoint of generator units.

            - "*hazards*": represents the hazards that the line might suffer (boolean vector) False: no hazard, nothing
              is done, True: a hazard, the powerline is disconnected
            - "*maintenance*": represents the maintenance operation performed on each powerline (boolean vector) False:
              no maintenance, nothing is done, True: a maintenance is scheduled, the powerline is disconnected
            - "*set_line_status*": a vector (int or float) to set the status of the powerline status (connected /
              disconnected) with the following interpretation:

                - 0: nothing is changed,
                - -1: disconnect the powerline,
                - +1: reconnect the powerline. If an action consists in "reconnecting" a powerline, and this same
                  powerline is affected by a maintenance or a hazard, it will be erased without any warning. "hazards"
                  and "maintenance" have the priority.

            - "change_line_status": a vector (bool) to change the status of the powerline. This vector should be
              interpreted as:

                - ``False``: do nothing
                - ``True``: change the status of the powerline: disconnect it if it was connected, connect it if it was
                  disconnected

            - "set_bus": (numpy int vector or dictionary) will set the buses to which the objects are connected. It
              follows a similar interpretation than the line status vector:

                - 0 -> don't change anything
                - +1 -> set to bus 1,
                - +2 -> set to bus 2, etc.
                - -1: You can use this method to disconnect an object by setting the value to -1.

            - "change_bus": (numpy bool vector or dictionary) will change the bus to which the object is connected.
              True will
              change it (eg switch it from bus 1 to bus 2 or from bus 2 to bus 1). NB this is only active if the system
              has only 2 buses per substation.

            - "redispatch": the best use of this is to specify either the numpy array of the redispatch vector you want
              to apply (that should have the size of the number of generators on the grid) or to specify a list of
              tuple, each tuple being 2 elements: first the generator ID, second the amount of redispatching,
              for example `[(1, -23), (12, +17)]`

            - "set_storage": the best use of this is to specify either the numpy array of the storage units vector
              you want
              to apply (that should have the size of the number of storage units on the grid) or to specify a list of
              tuple, each tuple being 2 elements: first the storage ID, second the amount of power you want to
              produce / absorb, for example `[(1, -23), (12, +17)]`

            **NB** the difference between "set_bus" and "change_bus" is the following:

              - If "set_bus" is 1, then the object (load, generator or powerline) will be moved to bus 1 of the
                substation to which it is connected. If it is already to bus 1 nothing will be done. If it's on another
                bus it will connect it to bus 1. It's disconnected, it will reconnect it and connect it to bus 1.
              - If "change_bus" is True, then objects will be moved from one bus to another. If the object were on bus 1
                then it will be moved on bus 2, and if it were on bus 2, it will be moved on bus 1. If the object is
                disconnected then the action is ambiguous, and calling it will throw an AmbiguousAction exception.

            **NB**: CHANGES: you can reconnect a powerline without specifying on each bus you reconnect it at both its
            ends. In that case the last known bus id for each its end is used.

            **NB**: if for a given powerline, both switch_line_status and set_line_status is set, the action will not
            be usable.
            This will lead to an :class:`grid2op.Exception.AmbiguousAction` exception.

            **NB**: The length of vectors provided here is NOT check in this function. This method can be "chained" and
            only on the final action, when used, eg. in the Backend, is checked.

            **NB**: If a powerline is disconnected, on maintenance, or suffer an outage, the associated "set_bus" will
            be ignored.
            Disconnection has the priority on anything. This priority is given because, in case of hazard, the hazard
            has the priority over the possible actions.

        Examples
        --------
        Here are short examples on how to update an action *eg.* how to create a valid :class:`Action` object that
        be used to modify a :class:`grid2op.Backend.Backend`.

        In all the following examples, we suppose that a valid grid2op environment is created, for example with:
        .. code-block:: python

            import grid2op
            # create a simple environment
            # and make sure every type of action can be used.
            env = grid2op.make(action_class=grid2op.Action.Action)

        *Example 1*: modify the load active values to set them all to 1. You can replace "load_p" by "load_q",
        "prod_p" or "prod_v" to change the load reactive value, the generator active setpoint or the generator
        voltage magnitude setpoint.

        .. code-block:: python

            new_load = np.ones(env.action_space.n_load)
            modify_load_active_value = env.action_space({"injection": {"load_p": new_load}})
            print(modify_load_active_value)

        *Example 2*: disconnect the powerline of id 1:

        .. code-block:: python

            disconnect_powerline = env.action_space({"set_line_status": [(1, -1)]})
            print(disconnect_powerline)
            # there is a shortcut to do that:
            disconnect_powerline2 = env.disconnect_powerline(line_id=1)

        *Example 3*: force the reconnection of the powerline of id 5 by connected it to bus 1 on its origin end and
        bus 2 on its extremity end.

        .. code-block:: python

            reconnect_powerline = env.action_space({"set_line_status": [(5, 1)],
                                                    "set_bus": {"lines_or_id": [(5, 1)]},
                                                    "set_bus": {"lines_ex_id": [(5, 2)]}
                                                     })
            print(reconnect_powerline)
            # and the shorter method:
            reconnect_powerline = env.action.space.reconnect_powerline(line_id=5, bus_or=1, bus_ex=2)

        *Example 4*: change the bus to which load 4 is connected:

        .. code-block:: python

            change_load_bus = env.action_space({"set_bus": {"loads_id": [(4, 1)]} })
            print(change_load_bus)

        *Example 5*: reconfigure completely substation 5, and connect the first 3 elements to bus 1 and the last 3
        elements to bus 2

        .. code-block:: python

            sub_id = 5
            target_topology = np.ones(env.sub_info[sub_id], dtype=dt_int)
            target_topology[3:] = 2
            reconfig_sub = env.action_space({"set_bus": {"substations_id": [(sub_id, target_topology)] } })
            print(reconfig_sub)

        *Example 6*: apply redispatching of +17.42 MW at generator with id 23 and -27.8 at generator with id 1

        .. code-block:: python

            redisp_act = env.action_space({"redispatch": [(23, +17.42), (23, -27.8)]})
            print(redisp_act)

        *Example 7*: apply an action on a storage unit: have the storage unit of id 0 produce 1.5MW

        .. code-block:: python

            storage_act = env.action_space({"set_storage": [(0, -1.5)]})
            print(storage_act)

        Returns
        -------
        self: :class:`BaseAction`
            Return the modified instance. This is handy to chain modifications if needed.

        """
        self._reset_vect()

        if dict_ is not None:
            for kk in dict_.keys():
                if kk not in self.authorized_keys:
                    warn = "The key \"{}\" used to update an action will be ignored. Valid keys are {}"
                    warn = warn.format(kk, self.authorized_keys)
                    warnings.warn(warn)

            self._digest_shunt(dict_)
            self._digest_injection(dict_)
            self._digest_redispatching(dict_)
            self._digest_storage(dict_)  # ADDED for battery
            self._digest_setbus(dict_)
            self._digest_change_bus(dict_)
            self._digest_set_status(dict_)
            self._digest_hazards(dict_)
            self._digest_maintenance(dict_)
            self._digest_change_status(dict_)

        return self

    def is_ambiguous(self):
        """
        Says if the action, as defined is ambiguous *per se* or not.

        See definition of :func:`BaseAction.check_space_legit` for more details about *ambiguity per se*.

        Returns
        -------
        res: ``True`` if the action is ambiguous, ``False`` otherwise.

        info: ``dict`` or not
            More information about the error. If the action is not ambiguous, it values to ``None``
        """
        try:
            self._check_for_ambiguity()
            res = False
            info = None
        except AmbiguousAction as exc_:
            info = exc_
            res = True
        return res, info

    def _check_for_ambiguity(self):
        """
        This method checks if an action is ambiguous or not. If the instance is ambiguous, an
        :class:`grid2op.Exceptions.AmbiguousAction` is raised.

        An action can be ambiguous in the following context:

          - It incorrectly affects the injections:

            - :code:`self._dict_inj["load_p"]` doesn't have the same size as the number of loads on the _grid.
            - :code:`self._dict_inj["load_q"]` doesn't have the same size as the number of loads on the _grid.
            - :code:`self._dict_inj["prod_p"]` doesn't have the same size as the number of loads on the _grid.
            - :code:`self._dict_inj["prod_v"]` doesn't have the same size as the number of loads on the _grid.

          - It affects the powerline in an incorrect manner:

            - :code:`self._switch_line_status` has not the same size as the number of powerlines
            - :code:`self._set_line_status` has not the same size as the number of powerlines
            - the status of some powerline is both *changed* (:code:`self._switch_line_status[i] == True` for some *i*)
              and *set* (:code:`self._set_line_status[i]` for the same *i* is not 0)
            - a powerline is both connected at one end (ex. its origin is set to bus 1) and disconnected at another
              (its extremity is set to bus -1)

          - It has an ambiguous behavior concerning the topology of some substations

            - the state of some bus for some element is both *changed* (:code:`self._change_bus_vect[i] = True` for
              some *i*) and *set* (:code:`self._set_topo_vect[i]` for the same *i* is not 0)
            - :code:`self._set_topo_vect` has not the same dimension as the number of elements on the powergrid
            - :code:`self._change_bus_vect` has not the same dimension as the number of elements on the powergrid

          - For redispatching, Ambiguous actions can come from:

            - Some redispatching action is active, yet
              :attr:`grid2op.Space.GridObjects.redispatching_unit_commitment_availble` is set to ``False``
            - the length of the redispatching vector :attr:`BaseAction._redispatching` is not compatible with the number
              of generators.
            - some redispatching are above the maximum ramp up :attr:`grid2op.Space.GridObjects.gen_max_ramp_up`
            - some redispatching are below the maximum ramp down :attr:`grid2op.Space.GridObjects.gen_max_ramp_down`
            - the redispatching action affect non dispatchable generators
            - the redispatching and the production setpoint, if added, are above pmax for at least a generator
            - the redispatching and the production setpoint, if added, are below pmin for at least a generator

        In case of need to overload this method, it is advise to still call this one from the base :class:`BaseAction`
        with ":code:`super()._check_for_ambiguity()`" or ":code:`BaseAction._check_for_ambiguity(self)`".

        Raises
        -------
        :class:`grid2op.Exceptions.AmbiguousAction`
            Or any of its more precise subclasses, depending on which assumption is not met.


        """
        if self._modif_change_status and self._modif_set_status and \
                np.any(self._set_line_status[self._switch_line_status] != 0):
            raise InvalidLineStatus("You asked to change the status (connected / disconnected) of a powerline by"
                                    " using the keyword \"change_status\" and set this same line state in "
                                    "\"set_status\" "
                                    "(or \"hazard\" or \"maintenance\"). This ambiguous behaviour is not supported")
        # check size
        if self._modif_inj:
            if "load_p" in self._dict_inj:
                if len(self._dict_inj["load_p"]) != self.n_load:
                    raise InvalidNumberOfLoads("This action acts on {} loads while there are {} "
                                               "in the _grid".format(len(self._dict_inj["load_p"]), self.n_load))
            if "load_q" in self._dict_inj:
                if len(self._dict_inj["load_q"]) != self.n_load:
                    raise InvalidNumberOfLoads("This action acts on {} loads while there are {} in "
                                               "the _grid".format(len(self._dict_inj["load_q"]), self.n_load))
            if "prod_p" in self._dict_inj:
                if len(self._dict_inj["prod_p"]) != self.n_gen:
                    raise InvalidNumberOfGenerators("This action acts on {} generators while there are {} in "
                                                    "the _grid".format(len(self._dict_inj["prod_p"]), self.n_gen))
            if "prod_v" in self._dict_inj:
                if len(self._dict_inj["prod_v"]) != self.n_gen:
                    raise InvalidNumberOfGenerators("This action acts on {} generators while there are {} in "
                                                    "the _grid".format(len(self._dict_inj["prod_v"]), self.n_gen))

        if len(self._switch_line_status) != self.n_line:
            raise InvalidNumberOfLines("This action acts on {} lines while there are {} in "
                                       "the _grid".format(len(self._switch_line_status), self.n_line))

        if len(self._set_topo_vect) != self.dim_topo:
            raise InvalidNumberOfObjectEnds("This action acts on {} ends of object while there are {} "
                                            "in the _grid".format(len(self._set_topo_vect), self.dim_topo))
        if len(self._change_bus_vect) != self.dim_topo:
            raise InvalidNumberOfObjectEnds("This action acts on {} ends of object while there are {} "
                                            "in the _grid".format(len(self._change_bus_vect), self.dim_topo))

        if len(self._redispatch) != self.n_gen:
            raise InvalidNumberOfGenerators("This action acts on {} generators (redispatching= while "
                                            "there are {} in the grid".format(len(self._redispatch), self.n_gen))

        # redispatching specific check
        if self._modif_redispatch:
            if not self.redispatching_unit_commitment_availble:
                raise UnitCommitorRedispachingNotAvailable("Impossible to use a redispatching action in this "
                                                           "environment. Please set up the proper costs for generator")

            if np.any(self._redispatch[~self.gen_redispatchable] != 0.):
                raise InvalidRedispatching("Trying to apply a redispatching action on a non redispatchable generator")

            if self._single_act:
                if np.any(self._redispatch > self.gen_max_ramp_up):
                   raise InvalidRedispatching("Some redispatching amount are above the maximum ramp up")
                if np.any(-self._redispatch > self.gen_max_ramp_down):
                   raise InvalidRedispatching("Some redispatching amount are bellow the maximum ramp down")

                if "prod_p" in self._dict_inj:
                    new_p = self._dict_inj["prod_p"]
                    tmp_p = new_p + self._redispatch
                    indx_ok = np.isfinite(new_p)
                    if np.any(tmp_p[indx_ok] > self.gen_pmax[indx_ok]):
                        raise InvalidRedispatching("Some redispatching amount, cumulated with the production setpoint, "
                                                   "are above pmax for some generator.")
                    if np.any(tmp_p[indx_ok] < self.gen_pmin[indx_ok]):
                        raise InvalidRedispatching("Some redispatching amount, cumulated with the production setpoint, "
                                                   "are below pmin for some generator.")

        # storage specific checks:
        self._is_storage_ambiguous()

        # topological action
        if self._modif_set_bus and self._modif_change_bus and np.any(self._set_topo_vect[self._change_bus_vect] != 0):
            raise InvalidBusStatus("You asked to change the bus of an object with"
                                   " using the keyword \"change_bus\" and set this same object state in \"set_bus\""
                                   ". This ambiguous behaviour is not supported")
        if self._modif_set_bus and np.any(self._set_topo_vect < -1):
            raise InvalidBusStatus("Invalid set_bus. Buses should be either -1 (disconnect), 0 (change nothing),"
                                   "1 (assign this object to bus one) or 2 (assign this object to bus"
                                   "2). A negative number has been found.")
        if self._modif_set_bus and np.any(self._set_topo_vect > 2):
            raise InvalidBusStatus("Invalid set_bus. Buses should be either -1 (disconnect), 0 (change nothing),"
                                   "1 (assign this object to bus one) or 2 (assign this object to bus"
                                   "2). A number higher than 2 has been found: substations with more than 2 busbars"
                                   "are not supported by grid2op at the moment. Do not hesitate to fill a feature "
                                   "request on github if you need this feature.")

        if False:
            # TODO find an elegant way to disable that
            # now it's possible.
            for q_id, status in enumerate(self._set_line_status):
                if status == 1:
                    # i reconnect a powerline, i need to check that it's connected on both ends
                    if self._set_topo_vect[self.line_or_pos_topo_vect[q_id]] == 0 or \
                            self._set_topo_vect[self.line_ex_pos_topo_vect[q_id]] == 0:

                        raise InvalidLineStatus("You ask to reconnect powerline {} yet didn't tell on"
                                                " which bus.".format(q_id))

        if self._modif_set_bus:
            disco_or = self._set_topo_vect[self.line_or_pos_topo_vect] == -1
            if np.any(self._set_topo_vect[self.line_ex_pos_topo_vect][disco_or] > 0):
                raise InvalidLineStatus("A powerline is connected (set to a bus at extremity end) and "
                                        "disconnected (set to bus -1 at origin end)")
            disco_ex = self._set_topo_vect[self.line_ex_pos_topo_vect] == -1
            if np.any(self._set_topo_vect[self.line_or_pos_topo_vect][disco_ex] > 0):
                raise InvalidLineStatus("A powerline is connected (set to a bus at origin end) and "
                                        "disconnected (set to bus -1 at extremity end)")

        # if i disconnected of a line, but i modify also the bus where it's connected
        if self._modif_set_bus or self._modif_change_bus:
            idx = self._set_line_status == -1
            id_disc = np.where(idx)[0]

        if self._modif_set_bus:
            if np.any(self._set_topo_vect[self.line_or_pos_topo_vect[id_disc]] > 0) or \
                    np.any(self._set_topo_vect[self.line_ex_pos_topo_vect[id_disc]] > 0):
                raise InvalidLineStatus("You ask to disconnect a powerline but also to connect it "
                                        "to a certain bus.")
        if self._modif_change_bus:
            if np.any(self._change_bus_vect[self.line_or_pos_topo_vect[id_disc]] > 0) or \
                    np.any(self._change_bus_vect[self.line_ex_pos_topo_vect[id_disc]] > 0):
                raise InvalidLineStatus("You ask to disconnect a powerline but also to change its bus.")

            if np.any(self._change_bus_vect[self.line_or_pos_topo_vect[self._set_line_status == 1]]):
                raise InvalidLineStatus("You ask to connect an origin powerline but also to *change* the bus  to which "
                                        "it  is connected. This is ambiguous. You must *set* this bus instead.")
            if np.any(self._change_bus_vect[self.line_ex_pos_topo_vect[self._set_line_status == 1]]):
                raise InvalidLineStatus("You ask to connect an extremity powerline but also to *change* the bus  to "
                                        "which it is connected. This is ambiguous. You must *set* this bus instead.")

        if self.shunts_data_available:
            if self.shunt_p.shape[0] != self.n_shunt:
                raise IncorrectNumberOfElements("Incorrect number of shunt (for shunt_p) in your action.")
            if self.shunt_q.shape[0] != self.n_shunt:
                raise IncorrectNumberOfElements("Incorrect number of shunt (for shunt_q) in your action.")
            if self.shunt_bus.shape[0] != self.n_shunt:
                raise IncorrectNumberOfElements("Incorrect number of shunt (for shunt_bus) in your action.")
            if self.n_shunt > 0:
                if np.max(self.shunt_bus) > 2:
                    raise AmbiguousAction("Some shunt is connected to a bus greater than 2")
                if np.min(self.shunt_bus) < -1:
                    raise AmbiguousAction("Some shunt is connected to a bus smaller than -1")
        else:
            # shunt is not available
            if self.shunt_p is not None:
                raise AmbiguousAction("Attempt to modify a shunt (shunt_p) while shunt data is not handled by backend")
            if self.shunt_q is not None:
                raise AmbiguousAction("Attempt to modify a shunt (shunt_q) while shunt data is not handled by backend")
            if self.shunt_bus is not None:
                raise AmbiguousAction("Attempt to modify a shunt (shunt_bus) while shunt data is not handled by backend")

    def _is_storage_ambiguous(self):
        """check if storage actions are ambiguous"""
        if self._modif_storage:
            if self.n_storage == 0:
                raise InvalidStorage("Attempt to modify a storage unit while there is none on the grid")
            if self._storage_power.shape[0] != self.n_storage:
                raise InvalidStorage("self._storage_power.shape[0] != self.n_storage: wrong number of storage "
                                     "units affected")
            if np.any(self._storage_power < -self.storage_max_p_prod):
                where_bug = np.where(self._storage_power < -self.storage_max_p_prod)[0]
                raise InvalidStorage(f"you asked a storage unit to absorb more than what it can: "
                                     f"self._storage_power[{where_bug}] < -self.storage_max_p_prod[{where_bug}].")
            if np.any(self._storage_power > self.storage_max_p_absorb):
                where_bug = np.where(self._storage_power < -self.storage_max_p_prod)[0]
                raise InvalidStorage(f"you asked a storage unit to produce more than what it can: "
                                     f"self._storage_power[{where_bug}] < -self.storage_max_p_prod[{where_bug}].")

        if "_storage_power" not in self.attr_list_set:
            if np.any(self._set_topo_vect[self.storage_pos_topo_vect] > 0):
                raise InvalidStorage("Attempt to modify bus (set) of a storage unit")
            if np.any(self._change_bus_vect[self.storage_pos_topo_vect]):
                raise InvalidStorage("Attempt to modify bus (change) of a storage unit")

    def _ignore_topo_action_if_disconnection(self, sel_):
        # force ignore of any topological actions
        self._set_topo_vect[np.array(self.line_or_pos_topo_vect[sel_])] = 0
        self._change_bus_vect[np.array(self.line_or_pos_topo_vect[sel_])] = False
        self._set_topo_vect[np.array(self.line_ex_pos_topo_vect[sel_])] = 0
        self._change_bus_vect[np.array(self.line_ex_pos_topo_vect[sel_])] = False

    def _obj_caract_from_topo_id(self, id_):
        obj_id = None
        objt_type = None
        array_subid = None
        for l_id, id_in_topo in enumerate(self.load_pos_topo_vect):
            if id_in_topo == id_:
                obj_id = l_id
                objt_type = "load"
                array_subid = self.load_to_subid
        if obj_id is None:
            for l_id, id_in_topo in enumerate(self.gen_pos_topo_vect):
                if id_in_topo == id_:
                    obj_id = l_id
                    objt_type = "generator"
                    array_subid = self.gen_to_subid
        if obj_id is None:
            for l_id, id_in_topo in enumerate(self.line_or_pos_topo_vect):
                if id_in_topo == id_:
                    obj_id = l_id
                    objt_type = self._line_or_str
                    array_subid = self.line_or_to_subid
        if obj_id is None:
            for l_id, id_in_topo in enumerate(self.line_ex_pos_topo_vect):
                if id_in_topo == id_:
                    obj_id = l_id
                    objt_type = self._line_ex_str
                    array_subid = self.line_ex_to_subid
        if obj_id is None:
            for l_id, id_in_topo in enumerate(self.storage_pos_topo_vect):
                if id_in_topo == id_:
                    obj_id = l_id
                    objt_type = "storage"
                    array_subid = self.storage_to_subid
        substation_id = array_subid[obj_id]
        return obj_id, objt_type, substation_id

    def __str__(self):
        """
        This utility allows printing in a human-readable format what objects will be impacted by the action.

        Returns
        -------
        str: :class:`str`
            The string representation of an :class:`BaseAction` in a human-readable format.

        Examples
        ---------

        It is simply the "print" function:

        .. code-block:: python

            action = env.action_space(...)
            print(action)

        """
        res = ["This action will:"]
        impact = self.impact_on_objects()

        # injections
        injection_impact = impact['injection']
        if injection_impact['changed']:
            for change in injection_impact['impacted']:
                res.append("\t - Set {} to {}".format(change['set'], change['to']))
        else:
            res.append("\t - NOT change anything to the injections")

        # redispatch
        if self._modif_redispatch:
            res.append("\t - Modify the generators with redispatching in the following way:")
            for gen_idx in range(self.n_gen):
                if self._redispatch[gen_idx] != 0.0:
                    gen_name = self.name_gen[gen_idx]
                    r_amount = self._redispatch[gen_idx]
                    res.append("\t \t - Redispatch \"{}\" of {:.2f} MW".format(gen_name, r_amount))
        else:
            res.append("\t - NOT perform any redispatching action")

        # storage
        if self._modif_storage:
            res.append("\t - Modify the storage units in the following way:")
            for stor_idx in range(self.n_storage):
                tmp = self._storage_power[stor_idx]
                if np.isfinite(tmp) and tmp != 0.:
                    name_ = self.name_storage[stor_idx]
                    amount_ = self._storage_power[stor_idx]
                    res.append("\t \t - Ask unit \"{}\" to {} {:.2f} MW (setpoint: {:.2f} MW)"
                               "".format(name_,
                                         "absorb" if amount_ > 0. else "produce",
                                         np.abs(amount_),
                                         amount_)
                               )
        else:
            res.append("\t - NOT modify any storage capacity")

        # force line status
        force_line_impact = impact['force_line']
        if force_line_impact['changed']:
            reconnections = force_line_impact['reconnections']
            if reconnections['count'] > 0:
                res.append("\t - Force reconnection of {} powerlines ({})"
                           .format(reconnections['count'], reconnections['powerlines']))

            disconnections = force_line_impact['disconnections']
            if disconnections['count'] > 0:
                res.append("\t - Force disconnection of {} powerlines ({})"
                           .format(disconnections['count'], disconnections['powerlines']))
        else:
            res.append("\t - NOT force any line status")

        # swtich line status
        swith_line_impact = impact['switch_line']
        if swith_line_impact['changed']:
            res.append("\t - Switch status of {} powerlines ({})"
                       .format(swith_line_impact['count'],
                               swith_line_impact['powerlines']))
        else:
            res.append("\t - NOT switch any line status")

        # topology
        bus_switch_impact = impact['topology']['bus_switch']
        if len(bus_switch_impact) > 0:
            res.append("\t - Change the bus of the following element(s):")
            for switch in bus_switch_impact:
                res.append("\t \t - Switch bus of {} id {} [on substation {}]"
                           .format(switch['object_type'], switch['object_id'],
                                   switch['substation']))
        else:
            res.append("\t - NOT switch anything in the topology")

        assigned_bus_impact = impact['topology']['assigned_bus']
        disconnect_bus_impact = impact['topology']['disconnect_bus']
        if len(assigned_bus_impact) > 0 or len(disconnect_bus_impact) > 0:
            if assigned_bus_impact:
                res.append("\t - Set the bus of the following element(s):")
            for assigned in assigned_bus_impact:
                res.append("\t \t - Assign bus {} to {} id {} [on substation {}]"
                           .format(assigned['bus'],
                                   assigned['object_type'],
                                   assigned['object_id'],
                                   assigned['substation']))
            if disconnect_bus_impact:
                res.append("\t - Disconnect the following element(s):")
            for disconnected in disconnect_bus_impact:
                res.append("\t - Disconnect {} id {} [on substation {}]"
                           .format(disconnected['object_type'],
                                   disconnected['object_id'],
                                   disconnected['substation']))
        else:
            res.append("\t - NOT force any particular bus configuration")
        return "\n".join(res)

    def impact_on_objects(self):
        """
        This will return a dictionary which contains details on objects that will be impacted by the action.

        Returns
        -------
        dict: :class:`dict`
            The dictionary representation of an action impact on objects

        """
        # handles actions on injections
        has_impact = False

        inject_detail = {
            'changed': False,
            'count': 0,
            'impacted': []
        }
        for k in ["load_p", "prod_p", "load_q", "prod_v"]:
            if k in self._dict_inj:
                inject_detail['changed'] = True
                has_impact = True
                inject_detail['count'] += 1
                inject_detail['impacted'].append({
                    'set': k,
                    'to': self._dict_inj[k]
                })

        # handles actions on force line status
        force_line_status = {
            'changed': False,
            'reconnections': {'count': 0, 'powerlines': []},
            'disconnections': {'count': 0, 'powerlines': []}
        }
        if np.any(self._set_line_status == 1):
            force_line_status['changed'] = True
            has_impact = True
            force_line_status['reconnections']['count'] = np.sum(self._set_line_status == 1)
            force_line_status['reconnections']['powerlines'] = np.where(self._set_line_status == 1)[0]

        if np.any(self._set_line_status == -1):
            force_line_status['changed'] = True
            has_impact = True
            force_line_status['disconnections']['count'] = np.sum(self._set_line_status == -1)
            force_line_status['disconnections']['powerlines'] = np.where(self._set_line_status == -1)[0]

        # handles action on swtich line status
        switch_line_status = {
            'changed': False,
            'count': 0,
            'powerlines': []
        }
        if np.sum(self._switch_line_status):
            switch_line_status['changed'] = True
            has_impact = True
            switch_line_status['count'] = np.sum(self._switch_line_status)
            switch_line_status['powerlines'] = np.where(self._switch_line_status)[0]

        topology = {
            'changed': False,
            'bus_switch': [],
            'assigned_bus': [],
            'disconnect_bus': []
        }
        # handles topology
        if np.any(self._change_bus_vect):
            for id_, k in enumerate(self._change_bus_vect):
                if k:
                    obj_id, objt_type, substation_id = self._obj_caract_from_topo_id(id_)
                    topology['bus_switch'].append({
                        'bus': k,
                        'object_type': objt_type,
                        'object_id': obj_id,
                        'substation': substation_id
                    })
            topology['changed'] = True
            has_impact = True

        if np.any(self._set_topo_vect != 0):
            for id_, k in enumerate(self._set_topo_vect):
                if k > 0:
                    obj_id, objt_type, substation_id = self._obj_caract_from_topo_id(id_)
                    topology['assigned_bus'].append({
                        'bus': k,
                        'object_type': objt_type,
                        'object_id': obj_id,
                        'substation': substation_id
                    })

                if k < 0:
                    obj_id, objt_type, substation_id = self._obj_caract_from_topo_id(id_)
                    topology['disconnect_bus'].append({
                        'bus': k,
                        'object_type': objt_type,
                        'object_id': obj_id,
                        'substation': substation_id
                    })
            topology['changed'] = True
            has_impact = True

        # handle redispatching
        redispatch = {
            "changed": False,
            "generators": []
        }
        if np.any(self._redispatch != 0.0):
            for gen_idx in range(self.n_gen):
                if self._redispatch[gen_idx] != 0.0:
                    gen_name = self.name_gen[gen_idx]
                    r_amount = self._redispatch[gen_idx]
                    redispatch["generators"].append({
                        "gen_id": gen_idx,
                        "gen_name": gen_name,
                        "amount": r_amount
                    })
            redispatch["changed"] = True
            has_impact = True

        storage = {"changed": False, "capacities": []}
        if self._modif_storage:
            for str_idx in range(self.n_storage):
                tmp = self._storage_power[str_idx]
                if np.isfinite(tmp):
                    name_ = self.name_storage[str_idx]
                    new_capacity = tmp
                    storage["capacities"].append({
                        "storage_id": str_idx,
                        "storage_name": name_,
                        "new_capacity": new_capacity
                    })
            storage["changed"] = True
            has_impact = True

        return {
            'has_impact': has_impact,
            'injection': inject_detail,
            'force_line': force_line_status,
            'switch_line': switch_line_status,
            'topology': topology,
            'redispatch': redispatch,
            "storage": storage
        }

    def as_dict(self):
        """
        Represent an action "as a" dictionary. This dictionary is useful to further inspect on which elements
        the actions had an impact. It is not recommended to use it as a way to serialize actions. The "do nothing"
        action should always be represented by an empty dictionary.

        The following keys (all optional) are present in the results:

          * `load_p`: if the action modifies the active loads.
          * `load_q`: if the action modifies the reactive loads.
          * `prod_p`: if the action modifies the active productions of generators.
          * `prod_v`: if the action modifies the voltage setpoint of generators.
          * `set_line_status` if the action tries to **set** the status of some powerlines. If present, this is a
            a dictionary with keys:

              * `nb_connected`: number of powerlines that are reconnected
              * `nb_disconnected`: number of powerlines that are disconnected
              * `connected_id`: the id of the powerlines reconnected
              * `disconnected_id`: the ids of the powerlines disconnected

          * `change_line_status`: if the action tries to **change** the status of some powerlines. If present, this
            is a dictionary with keys:

              * `nb_changed`: number of powerlines having their status changed
              * `changed_id`: the ids of the powerlines that are changed

          * `change_bus_vect`: if the action tries to **change** the topology of some substations. If present, this
            is a dictionary with keys:

              * `nb_modif_subs`: number of substations impacted by the action
              * `modif_subs_id`: ids of the substations impacted by the action
              * `change_bus_vect`: details the objects that are modified. It is itself a dictionary that represents for
                each impacted substations (keys) the modification of the objects connected to it.

          * `set_bus_vect`: if the action tries to **set** the topology of some substations. If present, this is a
            dictionary with keys:

              * `nb_modif_subs`: number of substations impacted by the action
              * `modif_subs_id`: the ids of the substations impacted by the action
              * `set_bus_vect`: details the objects that are modified. It is also a dictionary that represents for
                each impacted substations (keys) how the elements connected to it are impacted (their "new" bus)

          * `hazards` if the action is composed of some hazards. In this case, it's simply the index of the powerlines
            that are disconnected because of them.
          * `nb_hazards` the number of hazards the "action" implemented (eg number of powerlines disconnected because of
            hazards.
          * `maintenance` if the action is composed of some maintenance. In this case, it's simply the index of the
            powerlines that are affected by maintenance operation at this time step.
            that are disconnected because of them.
          * `nb_maintenance` the number of maintenance the "action" implemented eg the number of powerlines
            disconnected because of maintenance operations.
          * `redispatch` the redispatching action (if any). It gives, for each generator (all generator, not just the
            dispatchable one) the amount of power redispatched in this action.
          * `storage_power`: the setpoint for production / consumption for all storage units


        Returns
        -------
        res: ``dict``
            The action represented as a dictionary. See above for a description of it.

        """
        res = {}

        # saving the injections
        for k in ["load_p", "prod_p", "load_q", "prod_v"]:
            if k in self._dict_inj:
                res[k] = self._dict_inj[k]

        # handles actions on force line status
        if np.any(self._set_line_status != 0):
            res["set_line_status"] = {}
            res["set_line_status"]["nb_connected"] = np.sum(self._set_line_status == 1)
            res["set_line_status"]["nb_disconnected"] = np.sum(self._set_line_status == -1)
            res["set_line_status"]["connected_id"] = np.where(self._set_line_status == 1)[0]
            res["set_line_status"]["disconnected_id"] = np.where(self._set_line_status == -1)[0]

        # handles action on swtich line status
        if np.sum(self._switch_line_status):
            res["change_line_status"] = {}
            res["change_line_status"]["nb_changed"] = np.sum(self._switch_line_status)
            res["change_line_status"]["changed_id"] = np.where(self._switch_line_status)[0]

        # handles topology change
        if np.any(self._change_bus_vect):
            res["change_bus_vect"] = {}
            res["change_bus_vect"]["nb_modif_objects"] = np.sum(self._change_bus_vect)
            all_subs = set()
            for id_, k in enumerate(self._change_bus_vect):
                if k:
                    obj_id, objt_type, substation_id = self._obj_caract_from_topo_id(id_)
                    sub_id = "{}".format(substation_id)
                    if not sub_id in res["change_bus_vect"]:
                        res["change_bus_vect"][sub_id] = {}
                    res["change_bus_vect"][sub_id]["{}".format(obj_id)] = {"type": objt_type}
                    all_subs.add(sub_id)

            res["change_bus_vect"]["nb_modif_subs"] = len(all_subs)
            res["change_bus_vect"]["modif_subs_id"] = sorted(all_subs)

        # handles topology set
        if np.any(self._set_topo_vect):
            res["set_bus_vect"] = {}
            res["set_bus_vect"]["nb_modif_objects"] = np.sum(self._set_topo_vect)
            all_subs = set()
            for id_, k in enumerate(self._set_topo_vect):
                if k != 0:
                    obj_id, objt_type, substation_id = self._obj_caract_from_topo_id(id_)
                    sub_id = "{}".format(substation_id)
                    if not sub_id in res["set_bus_vect"]:
                        res["set_bus_vect"][sub_id] = {}
                    res["set_bus_vect"][sub_id]["{}".format(obj_id)] = {"type": objt_type, "new_bus": k}
                    all_subs.add(sub_id)

            res["set_bus_vect"]["nb_modif_subs"] = len(all_subs)
            res["set_bus_vect"]["modif_subs_id"] = sorted(all_subs)

        if np.any(self._hazards):
            res["hazards"] = np.where(self._hazards)[0]
            res["nb_hazards"] = np.sum(self._hazards)

        if np.any(self._maintenance):
            res["maintenance"] = np.where(self._maintenance)[0]
            res["nb_maintenance"] = np.sum(self._maintenance)

        if np.any(self._redispatch != 0.):
            res["redispatch"] = self._redispatch

        if self._modif_storage:
            res["storage_power"] = self._storage_power

        return res

    def get_types(self):
        """
        Shorthand to get the type of an action. The type of an action is among:

        - "injection": does this action modifies load or generator active values
        - "voltage": does this action modifies the generator voltage setpoint or the shunts
        - "topology": does this action modifies the topology of the grid (*ie* set or switch some buses)
        - "line": does this action modifies the line status
        - "redispatching" does this action modifies the redispatching
        - "storage" does this action impact the production / consumption of storage units

        Notes
        ------

        A single action can be of multiple types.

        The `do nothing` has no type at all.

        If a line only set / change the status of a powerline then it does not count as a topological
        modification.

        If the bus to which a storage unit is connected is modified, but there is no setpoint for
        the production / consumption of any storage units, then the action is **NOT** taged as
        an action on the storage units.

        Returns
        -------
        injection: ``bool``
            Does it affect load or generator active value
        voltage: ``bool``
            Does it affect the voltage
        topology: ``bool``
            Does it affect the topology (line status change / switch are **NOT** counted as topology)
        line: ``bool``
            Does it affect the line status (line status change / switch are **NOT** counted as topology)
        redispatching: ``bool``
            Does it performs (explicitly) any redispatching
        storage: ``bool``
            Does it performs (explicitly) any action on the storage production / consumption

        """
        injection = "load_p" in self._dict_inj or "prod_p" in self._dict_inj
        voltage = "prod_v" in self._dict_inj
        if self.shunts_data_available:
            voltage = voltage or np.any(np.isfinite(self.shunt_p))
            voltage = voltage or np.any(np.isfinite(self.shunt_q))
            voltage = voltage or np.any(self.shunt_bus != 0)

        lines_impacted, subs_impacted = self.get_topological_impact()
        topology = np.any(subs_impacted)
        line = np.any(lines_impacted)
        redispatching = np.any(self._redispatch != 0.)
        storage = self._modif_storage
        return injection, voltage, topology, line, redispatching, storage

    def _aux_effect_on_load(self, load_id):
        if load_id >= self.n_load:
            raise Grid2OpException(f"There are only {self.n_load} loads on the grid. Cannot check impact on "
                                   f"`load_id={load_id}`")
        if load_id < 0:
            raise Grid2OpException(f"`load_id` should be positive.")
        res = {"new_p": np.NaN, "new_q": np.NaN, "change_bus": False, "set_bus": 0}
        if "load_p" in self._dict_inj:
            res["new_p"] = self._dict_inj["load_p"][load_id]
        if "load_q" in self._dict_inj:
            res["new_q"] = self._dict_inj["load_q"][load_id]
        my_id = self.load_pos_topo_vect[load_id]
        res["change_bus"] = self._change_bus_vect[my_id]
        res["set_bus"] = self._set_topo_vect[my_id]
        return res

    def _aux_effect_on_gen(self, gen_id):
        if gen_id >= self.n_gen:
            raise Grid2OpException(f"There are only {self.n_gen} gens on the grid. Cannot check impact on "
                                   f"`gen_id={gen_id}`")
        if gen_id < 0:
            raise Grid2OpException(f"`gen_id` should be positive.")
        res = {"new_p": np.NaN, "new_v": np.NaN, "set_bus": 0, "change_bus": False}
        if "prod_p" in self._dict_inj:
            res["new_p"] = self._dict_inj["prod_p"][gen_id]
        if "prod_v" in self._dict_inj:
            res["new_v"] = self._dict_inj["prod_v"][gen_id]
        my_id = self.gen_pos_topo_vect[gen_id]
        res["change_bus"] = self._change_bus_vect[my_id]
        res["set_bus"] = self._set_topo_vect[my_id]
        res["redispatch"] = self._redispatch[gen_id]
        return res

    def _aux_effect_on_line(self, line_id):
        if line_id >= self.n_line:
            raise Grid2OpException(f"There are only {self.n_line} powerlines on the grid. Cannot check impact on "
                                   f"`line_id={line_id}`")
        if line_id < 0:
            raise Grid2OpException(f"`line_id` should be positive.")
        res = {}
        # origin topology
        my_id = self.line_or_pos_topo_vect[line_id]
        res["change_bus_or"] = self._change_bus_vect[my_id]
        res["set_bus_or"] = self._set_topo_vect[my_id]
        # extremity topology
        my_id = self.line_ex_pos_topo_vect[line_id]
        res["change_bus_ex"] = self._change_bus_vect[my_id]
        res["set_bus_ex"] = self._set_topo_vect[my_id]
        # status
        res["set_line_status"] = self._set_line_status[line_id]
        res["change_line_status"] = self._switch_line_status[line_id]
        return res

    def _aux_effect_on_storage(self, storage_id):
        if storage_id >= self.n_storage:
            raise Grid2OpException(f"There are only {self.n_storage} storage units on the grid. "
                                   f"Cannot check impact on "
                                   f"`storage_id={storage_id}`")
        if storage_id < 0:
            raise Grid2OpException(f"`storage_id` should be positive.")
        res = {"power": np.NaN, "set_bus": 0, "change_bus": False}
        my_id = self.storage_pos_topo_vect[storage_id]
        res["change_bus"] = self._change_bus_vect[my_id]
        res["set_bus"] = self._set_topo_vect[my_id]
        res["power"] = self._storage_power[storage_id]
        return res

    def _aux_effect_on_substation(self, substation_id):
        if substation_id >= self.n_sub:
            raise Grid2OpException(f"There are only {self.n_sub} substations on the grid. "
                                   f"Cannot check impact on "
                                   f"`substation_id={storage_id}`")
        if substation_id < 0:
            raise Grid2OpException(f"`substation_id` should be positive.")

        res = {}
        beg_ = int(np.sum(self.sub_info[:substation_id]))
        end_ = int(beg_ + self.sub_info[substation_id])
        res["change_bus"] = self._change_bus_vect[beg_:end_]
        res["set_bus"] = self._set_topo_vect[beg_:end_]
        return res

    def effect_on(self, _sentinel=None, load_id=None, gen_id=None, line_id=None, substation_id=None,
                  storage_id=None):
        """
        Return the effect of this action on a unique given load, generator unit, powerline or substation.
        Only one of load, gen, line or substation should be filled.

        The query of these objects can only be done by id here (ie by giving the integer of the object in the backed).
        The :class:`ActionSpace` has some utilities to access them by name too.

        Parameters
        ----------
        _sentinel: ``None``
            Used to prevent positional parameters. Internal, **do not use**.

        load_id: ``int``
            The ID of the load we want to inspect

        gen_id: ``int``
            The ID of the generator we want to inspect

        line_id: ``int``
            The ID of the powerline we want to inspect

        substation_id: ``int``
            The ID of the substation we want to inspect

        storage_id: ``int``
            The ID of the storage unit we want to inspect

        Returns
        -------
        res: :class:`dict`
            A dictionary with keys and value depending on which object needs to be inspected:

            - if a load is inspected, then the keys are:

                - "new_p" the new load active value (or NaN if it doesn't change),
                - "new_q" the new load reactive value (or Nan if nothing has changed from this point of view)
                - "set_bus" the new bus where the load will be moved (int: id of the bus, 0 no change, -1 disconnected)
                - "change_bus" whether or not this load will be moved from one bus to another (for example is an action
                  asked it to go from bus 1 to bus 2)

            - if a generator is inspected, then the keys are:

                - "new_p" the new generator active setpoint value (or NaN if it doesn't change),
                - "new_v" the new generator voltage setpoint value (or Nan if nothing has changed from this point of
                  view)
                - "set_bus" the new bus where the load will be moved (int: id of the bus, 0 no change, -1 disconnected)
                - "change_bus" whether or not this load will be moved from one bus to another (for example is an action
                  asked it to go from bus 1 to bus 2)
                - "redispatch" the amount of power redispatched for this generator.

            - if a powerline is inspected then the keys are:

                - "change_bus_or": whether or not the origin end will be moved from one bus to another
                - "change_bus_ex": whether or not the extremity end will be moved from one bus to another
                - "set_bus_or": the new bus where the origin will be moved
                - "set_bus_ex": the new bus where the extremity will be moved
                - "set_line_status": the new status of the power line
                - "change_line_status": whether or not to switch the status of the powerline

            - if a substation is inspected, it returns the topology to this substation in a dictionary with keys:

                - "change_bus"
                - "set_bus"

            - if a storage unit is inspected, it returns a dictionary with:

                - "change_bus"
                - "set_bus"
                - "power" : the power you want to produce  / absorb with the storage unit ( if < 0 the power is
                  produced, if > 0 then power is absorbed)

        NB the difference between "set_bus" and "change_bus" is the following:

            - If "set_bus" is 1, then the object (load, generator or powerline) will be moved to bus 1 of the substation
              to which it is connected. If it is already to bus 1 nothing will be done. If it's on another bus it will
              connect it to bus 1. It's disconnected, it will reconnect it and connect it to bus 1.
            - If "change_bus" is True, then the object will be moved from one bus to another. If the object were on
              bus 1
              then it will be moved on bus 2, and if it were on bus 2, it will be moved on bus 1. If the object were
              disconnected, then it will be connected to the affected bus.

        Raises
        ------
        :class:`grid2op.Exception.Grid2OpException`
            If _sentinel is modified, or if none of the arguments are set or alternatively if 2 or more of the
            parameters are being set.

        """
        EXCEPT_TOO_MUCH_ELEMENTS = "You can only the inspect the effect of an action on one single element"
        if _sentinel is not None:
            raise Grid2OpException("action.effect_on should only be called with named argument.")

        if load_id is None and gen_id is None and line_id is None and storage_id is None and substation_id is None:
            raise Grid2OpException("You ask the effect of an action on something, without provided anything")

        if load_id is not None:
            if gen_id is not None or line_id is not None or storage_id is not None or substation_id is not None:
                raise Grid2OpException(EXCEPT_TOO_MUCH_ELEMENTS)
            res = self._aux_effect_on_load(load_id)

        elif gen_id is not None:
            if line_id is not None or storage_id is not None or substation_id is not None:
                raise Grid2OpException(EXCEPT_TOO_MUCH_ELEMENTS)
            res = self._aux_effect_on_gen(gen_id)

        elif line_id is not None:
            if storage_id is not None or substation_id is not None:
                raise Grid2OpException(EXCEPT_TOO_MUCH_ELEMENTS)
            res = self._aux_effect_on_line(line_id)

        elif storage_id is not None:
            if substation_id is not None:
                raise Grid2OpException("You can only the inspect the effect of an action on one single element")
            res = self._aux_effect_on_storage(storage_id)

        else:
            res = self._aux_effect_on_substation(substation_id)
        return res

    def get_storage_modif(self):
        """
        Retrieve the modification that will be performed on all the storage unit

        Returns
        -------
        storage_power: ``np.ndarray``
            New storage power target (Nan = not modified, otherwise the setpoint given) [in MW]
        storage_set_bus: ``np.ndarray``
            New bus of the storage units, affected with "set_bus" command (0 = not affected, -1 = disconnected)
        storage_change_bus: ``np.ndarray``
            New bus of the storage units, affected with "change_bus" command

        """
        storage_power = 1.0 * self._storage_power
        storage_set_bus = 1 * self._set_topo_vect[self.storage_pos_topo_vect]
        storage_change_bus = copy.deepcopy(self._change_bus_vect[self.storage_pos_topo_vect])
        return storage_power, storage_set_bus, storage_change_bus

    def get_load_modif(self):
        """
        Retrieve the modification that will be performed on all the loads

        Returns
        -------
        load_p: ``np.ndarray``
            New load p (Nan = not modified) [in MW]
        load_q: ``np.ndarray``
            New load q (Nan = not modified) [in MVaR]
        load_set_bus: ``np.ndarray``
            New bus of the loads, affected with "set_bus" command
        load_change_bus: ``np.ndarray``
            New bus of the loads, affected with "change_bus" command
        """
        load_p = np.full(self.n_load, fill_value=np.NaN, dtype=dt_float)
        if "load_p" in self._dict_inj:
            load_p[:] = self._dict_inj["load_p"]
        load_q = 1.0 * load_p
        if "load_q" in self._dict_inj:
            load_q[:] = self._dict_inj["load_q"]
        load_set_bus = 1 * self._set_topo_vect[self.load_pos_topo_vect]
        load_change_bus = copy.deepcopy(self._change_bus_vect[self.load_pos_topo_vect])
        return load_p, load_q, load_set_bus, load_change_bus

    def get_gen_modif(self):
        """
        Retrieve the modification that will be performed on all the generators

        Returns
        -------
        gen_p: ``np.ndarray``
            New gen p (Nan = not modified) [in MW]
        gen_v: ``np.ndarray``
            New gen v setpoint (Nan = not modified) [in kV]
        gen_set_bus: ``np.ndarray``
            New bus of the generators, affected with "set_bus" command
        gen_change_bus: ``np.ndarray``
            New bus of the generators, affected with "change_bus" command

        """
        gen_p = np.full(self.n_load, fill_value=np.NaN, dtype=dt_float)
        if "prod_p" in self._dict_inj:
            gen_p[:] = self._dict_inj["prod_p"]
        gen_v = 1.0 * gen_p
        if "prod_v" in self._dict_inj:
            gen_v[:] = self._dict_inj["prod_v"]
        gen_set_bus = 1 * self._set_topo_vect[self.gen_pos_topo_vect]
        gen_change_bus = copy.deepcopy(self._change_bus_vect[self.gen_pos_topo_vect])
        return gen_p, gen_v, gen_set_bus, gen_change_bus

    # TODO do the get_line_modif, get_line_or_modif and get_line_ex_modif

    def _aux_affect_object_int(self, values, name_el, nb_els,
                               name_els,
                               inner_vect,
                               outer_vect,
                               min_val=-1,
                               max_val=2,
                               ):
        """
        NB : this do not set the _modif_set_bus attribute. It is expected to be set in the property setter.
        This is not set here, because it's recursive and if it fails at a point, it would be set for nothing

        values: the new values to set
        name_el: "load"
        nb_els: self.n_load
        inner_vect: self.load_pos_topo_vect
        name_els: self.name_load
        outer_vect: self._set_topo_vect

        will modify outer_vect[inner_vect]
        """
        if isinstance(values, tuple):
            # i provide a tuple: load_id, new_bus
            if len(values) != 2:
                raise IllegalAction(f"when set with tuple, this tuple should have size 2 and be: {name_el}_id, new_bus "
                                    f"eg. (3, {max_val})")
            el_id, new_bus = values
            try:
                new_bus = int(new_bus)
            except Exception as exc_:
                raise IllegalAction(f"new_bus should be convertible to integer. Error was : \"{exc_}\"")

            if new_bus < min_val:
                raise IllegalAction(f"new_bus should be between {min_val} and {max_val}")
            if new_bus > max_val:
                raise IllegalAction(f"new_bus should be between {min_val} and {max_val}")

            if isinstance(el_id, (float, dt_float, np.float64)):
                raise IllegalAction(f"{name_el}_id should be integers you provided float!")
            if isinstance(el_id, (bool, dt_bool)):
                raise IllegalAction(f"{name_el}_id should be integers you provided bool!")
            if isinstance(el_id, str):
                raise IllegalAction(f"{name_el}_id should be integers you provided string "
                                    f"(hint: you can use a dictionary to set the bus by name eg. "
                                    f"act.{name_el}_set_bus = {{act.name_{name_el}[0] : 1, act.name_{name_el}[1] : "
                                    f"{max_val}}} )!")

            try:
                el_id = int(el_id)
            except Exception as exc_:
                raise IllegalAction(f"{name_el}_id should be convertible to integer. Error was : \"{exc_}\"")
            if el_id < 0:
                raise IllegalAction(f"Impossible to set the bus of a {name_el} with negative id")
            if el_id >= nb_els:
                raise IllegalAction(f"Impossible to set a {name_el} id {el_id} because there are only "
                                    f"{nb_els} on the grid (and in python id starts at 0)")
            outer_vect[inner_vect[el_id]] = new_bus
            return
        elif isinstance(values, np.ndarray):
            if isinstance(values.dtype, float) or values.dtype == dt_float or values.dtype == np.float64:
                raise IllegalAction(f"{name_el}_id should be integers you provided float!")
            if isinstance(values.dtype, bool) or values.dtype == dt_bool:
                raise IllegalAction(f"{name_el}_id should be integers you provided boolean!")

            try:
                values = values.astype(dt_int)
            except Exception as exc_:
                raise IllegalAction(f"{name_el}_id should be convertible to integer. Error was : \"{exc_}\"")
            if np.any(values < min_val):
                raise IllegalAction(f"new_bus should be between {min_val} and {max_val}, found a value < {min_val}")
            if np.any(values > max_val):
                raise IllegalAction(f"new_bus should be between {min_val} and {max_val}, found a value  > {max_val}")
            outer_vect[inner_vect] = values
            return
        elif isinstance(values, list):
            # 2 cases: list of tuple, or list (convertible to numpy array)
            if len(values) == nb_els:
                # 2 cases: either i set all loads in the form [(0,..), (1,..), (2,...)]
                # or i should have converted the list to np array
                if isinstance(values[0], tuple):
                    # list of tuple, handled below
                    # TODO can be somewhat "hacked" if the type of the object on the list is not always the same
                    pass
                else:
                    # get back to case where it's a full vector
                    values = np.array(values)
                    self._aux_affect_object_int(values, name_el, nb_els, name_els,
                                                inner_vect=inner_vect, outer_vect=outer_vect,
                                                min_val=min_val, max_val=max_val)
                    return

            # expected list of tuple, each tuple is a pair with load_id, new_load_bus: example: [(0, 1), (2,2)]
            for el in values:
                if len(el) != 2:
                    raise IllegalAction(f"If input is a list, it should be a  list of pair (el_id, new_bus) "
                                        f"eg. [(0, {max_val}), (2, {min_val})]")
                el_id, new_bus = el
                if isinstance(el_id, str) and name_els is not None:
                    tmp = np.where(name_els == el_id)[0]
                    if len(tmp) == 0:
                        raise IllegalAction(f"No known {name_el} with name {el_id}")
                    el_id = tmp[0]
                self._aux_affect_object_int((el_id, new_bus), name_el, nb_els, name_els,
                                            inner_vect=inner_vect, outer_vect=outer_vect,
                                            min_val=min_val, max_val=max_val)
        elif isinstance(values, dict):
            # 2 cases: either key = load_id and value = new_bus or key = load_name and value = new bus
            for key, new_bus in values.items():
                if isinstance(key, str) and name_els is not None:
                    tmp = np.where(name_els == key)[0]
                    if len(tmp) == 0:
                        raise IllegalAction(f"No known {name_el} with name {key}")
                    key = tmp[0]
                self._aux_affect_object_int((key, new_bus), name_el, nb_els, name_els,
                                            inner_vect=inner_vect, outer_vect=outer_vect,
                                            min_val=min_val, max_val=max_val)
        else:
            raise IllegalAction(f"Impossible to modify the {name_el} bus with inputs {values}. "
                                f"Please see the documentation.")

    @property
    def load_set_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which each storage unit is **set**.

        It behaves similarly as :attr:`BaseAction.gen_set_bus`. See the help there for more information.
        """
        res = self.set_bus[self.load_pos_topo_vect]
        res.flags.writeable = False
        return res

    @load_set_bus.setter
    def load_set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the load bus (with \"set\") with this action type.")
        orig_ = self.load_set_bus
        try:
            self._aux_affect_object_int(values, "load", self.n_load, self.name_load,
                                        self.load_pos_topo_vect, self._set_topo_vect)
            self._modif_set_bus = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, "load", self.n_load, self.name_load,
                                        self.load_pos_topo_vect, self._set_topo_vect)
            raise IllegalAction(f"Impossible to modify the load bus with your input. Please consult the documentation. "
                                f"The error was \"{exc_}\"")

    @property
    def gen_set_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the action **set** the generator units.

        Returns
        -------
        res:
            A vector of integer, of size `act.n_gen` indicating what type of action is performed for
            each generator units with the convention :

            * 0 the action do not action on this storage unit
            * -1 the action disconnect the storage unit
            * 1 the action set the storage unit to busbar 1
            * 2 the action set the storage unit to busbar 2

        Examples
        --------

        To retrieve the impact of the action on the storage unit, you can do:

        .. code-block:: python

            gen_buses = act.gen_set_bus

        To modify these buses with **set** you can do:

        .. code-block:: python

            # create an environment where i can modify everything
            import numpy as np
            import grid2op
            from grid2op.Action import CompleteAction
            env = grid2op.make("educ_case14_storage", test=True, action_class=CompleteAction)

            # create an action
            act = env.action_space()

            # method 1 : provide the full vector
            act.gen_set_bus = np.ones(act.n_gen, dtype=int)

            # method 2: provide the index of the unit you want to modify
            act.gen_set_bus = (1, 2)

            # method 3: provide a list of the units you want to modify
            act.gen_set_bus = [(1, 2), (0, -1)]

            # method 4: change the storage unit by their name with a dictionary
            act.gen_set_bus = {"gen_1_0": 2}

        .. note:: The "rule of thumb" to modify an object using "set" method it to provide always
            the ID of an object AND its value. The ID should be an integer (or a name in some cases)
            and the value an integer representing on which busbar to put the new element.

        Notes
        -----
        It is a "property", you don't have to use parenthesis to access it:

        .. code-block:: python

            # valid code
            gen_buses = act.gen_set_bus

            # invalid code, it will crash, do not run
            gen_buses = act.gen_set_bus()
            # end do not run

        And neither should you uses parenthesis to modify it:

        .. code-block:: python

            # valid code
            act.gen_set_bus = [(1, 2), (0, -1)]

            # invalid code, it will crash, do not run
            act.gen_set_bus([(1, 2), (0, -1)])
            # end do not run

        Property cannot be set "directly", you have to use the `act.XXX = ...` syntax. For example:

        .. code-block:: python

            # valid code
            act.gen_set_bus = [(1, 2), (0, -1)]

            # invalid code, it will raise an error, and even if it did not it would have not effect
            # do not run
            act.gen_set_bus[1] = 2
            # end do not run

        .. note:: Be careful not to mix "change" and "set". For "change" you only need to provide the ID of the elements
            you want to change, for "set" you need to provide the ID **AND** where you want to set them.

        """
        res = self.set_bus[self.gen_pos_topo_vect]
        res.flags.writeable = False
        return res

    @gen_set_bus.setter
    def gen_set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the gen bus (with \"set\") with this action type.")
        orig_ = self.gen_set_bus
        try:
            self._aux_affect_object_int(values, "gen", self.n_gen, self.name_gen,
                                        self.gen_pos_topo_vect, self._set_topo_vect)
            self._modif_set_bus = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, "gen", self.n_gen, self.name_gen,
                                        self.gen_pos_topo_vect, self._set_topo_vect)
            raise IllegalAction(f"Impossible to modify the gen bus with your input. Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def storage_set_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which each storage unit is **set**.

        It behaves similarly as :attr:`BaseAction.gen_set_bus`. See the help there for more information.
        """
        if "set_storage" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the storage bus (with \"set\") with this action type.")
        res = self.set_bus[self.storage_pos_topo_vect]
        res.flags.writeable = False
        return res

    @storage_set_bus.setter
    def storage_set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the storage bus (with \"set\") with this action type.")
        if "set_storage" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the storage bus (with \"set\") with this action type.")
        orig_ = self.storage_set_bus
        try:
            self._aux_affect_object_int(values, "storage", self.n_storage, self.name_storage,
                                        self.storage_pos_topo_vect, self._set_topo_vect)
            self._modif_set_bus = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, "storage", self.n_storage, self.name_storage,
                                        self.storage_pos_topo_vect, self._set_topo_vect)
            raise IllegalAction(f"Impossible to modify the storage bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def line_or_set_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the origin side of each powerline is **set**.

        It behaves similarly as :attr:`BaseAction.gen_set_bus`. See the help there for more information.
        """
        res = self.set_bus[self.line_or_pos_topo_vect]
        res.flags.writeable = False
        return res

    @line_or_set_bus.setter
    def line_or_set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the line (origin) bus (with \"set\") with this action type.")
        orig_ = self.line_or_set_bus
        try:
            self._aux_affect_object_int(values, self._line_or_str, self.n_line, self.name_line,
                                        self.line_or_pos_topo_vect, self._set_topo_vect)
            self._modif_set_bus = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, self._line_or_str, self.n_line, self.name_line,
                                        self.line_or_pos_topo_vect, self._set_topo_vect)
            raise IllegalAction(f"Impossible to modify the line origin bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def line_ex_set_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the extremity side of each powerline is **set**.

        It behaves similarly as :attr:`BaseAction.gen_set_bus`. See the help there for more information.
        """
        res = self.set_bus[self.line_ex_pos_topo_vect]
        res.flags.writeable = False
        return res

    @line_ex_set_bus.setter
    def line_ex_set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the line (ex) bus (with \"set\") with this action type.")
        orig_ = self.line_ex_set_bus
        try:
            self._aux_affect_object_int(values, self._line_ex_str, self.n_line, self.name_line,
                                        self.line_ex_pos_topo_vect, self._set_topo_vect)
            self._modif_set_bus = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, self._line_ex_str, self.n_line, self.name_line,
                                        self.line_ex_pos_topo_vect, self._set_topo_vect)
            raise IllegalAction(f"Impossible to modify the line extrmity bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def set_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which any element is **set**.

        It behaves similarly as :attr:`BaseAction.gen_set_bus` and can be use to modify any elements type
        as opposed to the more specific :attr:`BaseAction.gen_set_bus`, :attr:`BaseAction.load_set_bus`,
        :attr:`BaseAction.line_or_set_bus`, :attr:`BaseAction.line_ex_set_bus` or
        :attr:`BaseAction.storage_set_bus` that are specific to a certain type of objects.

        Notes
        -----

        For performance reasons, it do not allow to modify the elements by there names.

        The order of each elements are given in the :attr:`grid2op.Space.GridObjects.gen_pos_topo_vect`,
        :attr:`grid2op.Space.GridObjects.load_pos_topo_vect`,
        :attr:`grid2op.Space.GridObjects.line_or_pos_topo_vect`,
        :attr:`grid2op.Space.GridObjects.line_ex_pos_topo_vect` or
        :attr:`grid2op.Space.GridObjects.storage_pos_topo_vect`

        For example:

        .. code-block:: python

            act.set_bus = [(0,1), (1, -1), (3, 2)]

        Will:

          * set to bus 1 the (unique) element for which \*_pos_topo_vect is 1
          * disconnect the (unique) element for which \*_pos_topo_vect is 2
          * set to bus 2 the (unique) element for which \*_pos_topo_vect is 3

        You can use the documentation page :ref:`modeled-elements-module` for more information about which
        element correspond to what component of this vector.

        """
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the bus (with \"set\") with this action type.")
        res = 1 * self._set_topo_vect
        res.flags.writeable = False
        return res

    @set_bus.setter
    def set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the bus (with \"set\") with this action type.")
        orig_ = self.set_bus
        try:
            self._aux_affect_object_int(values, "", self.dim_topo, None,
                                        np.arange(self.dim_topo), self._set_topo_vect)
            self._modif_set_bus = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, "", self.dim_topo, None,
                                        np.arange(self.dim_topo), self._set_topo_vect)
            raise IllegalAction(f"Impossible to modify the bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def line_set_status(self):
        """
        Property to set the status of the powerline.

        It behave similarly than :attr:`BaseAction.gen_set_bus` but with the following convention:

        * 0 still means it is not affected
        * +1 means that we force the connection on a powerline
        * -1 means we force the disconnection of a powerline

        Notes
        -----

        Setting a status of a powerline to +2 will raise an error.

        Examples
        ---------

        For example:

        .. code-block:: python

            act.line_set_status = [(0,1), (1, -1), (3, 1)]

        Will force the reconnection of line id 0 and 1 and force disconnection of line id 1.

        """
        if "set_line_status" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the status of powerlines (with \"set\") with this action type.")
        res = 1 * self._set_line_status
        res.flags.writeable = False
        return res

    @line_set_status.setter
    def line_set_status(self, values):
        if "set_line_status" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the status of powerlines (with \"set\") with this action type.")
        orig_ = 1 * self._set_line_status
        try:
            self._aux_affect_object_int(values, "line status", self.n_line, self.name_line,
                                        np.arange(self.n_line), self._set_line_status,
                                        max_val=1)
            self._modif_set_status = True
        except Exception as exc_:
            self._aux_affect_object_int(orig_, "line status", self.n_line, self.name_line,
                                        np.arange(self.n_line), self._set_line_status,
                                        max_val=1)
            raise IllegalAction(f"Impossible to modify the line status with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    def _aux_affect_object_bool(self, values, name_el, nb_els,
                                name_els,
                                inner_vect,
                                outer_vect
                                ):
        """
        NB : this do not set the _modif_set_bus attribute. It is expected to be set in the property setter.
        This is not set here, because it's recursive and if it fails at a point, it would be set for nothing

        values: the new values to set
        name_el: "load"
        nb_els: self.n_load
        inner_vect: self.load_pos_topo_vect
        name_els: self.name_load
        outer_vect: self._change_bus_vect

        will modify outer_vect[inner_vect]
        """
        if isinstance(values, bool):
            # to make it explicit, tuple modifications are deactivated
            raise IllegalAction(f"Impossible to change a {name_el} with a tuple input. Accepted inputs are:"
                                f"int, list of int, list of string, array of int, array of bool, set of int,"
                                f"set of string")
        elif isinstance(values, float):
            # to make it explicit, tuple modifications are deactivated
            raise IllegalAction(f"Impossible to change a {name_el} with a tuple input. Accepted inputs are:"
                                f"int, list of int, list of string, array of int, array of bool, set of int,"
                                f"set of string")
        elif isinstance(values, (int, dt_int, np.int64)):
            # i provide an int: load_id
            try:
                el_id = int(values)
            except Exception as exc_:
                raise IllegalAction(f"{name_el}_id should be convertible to integer. Error was : \"{exc_}\"")
            if el_id < 0:
                raise IllegalAction(f"Impossible to change a negative {name_el} with negative id")
            if el_id >= nb_els:
                raise IllegalAction(f"Impossible to change a {name_el} id {el_id} because there are only "
                                    f"{nb_els} on the grid (and in python id starts at 0)")
            outer_vect[inner_vect[el_id]] = not outer_vect[inner_vect[el_id]]
            return
        elif isinstance(values, tuple):
            # to make it explicit, tuple modifications are deactivated
            raise IllegalAction(f"Impossible to change a {name_el} with a tuple input. Accepted inputs are:"
                                f"int, list of int, list of string, array of int, array of bool, set of int,"
                                f"set of string")
        elif isinstance(values, np.ndarray):
            # either the int id i need to change or the full value.
            if isinstance(values.dtype, bool) or values.dtype == dt_bool or values.dtype == bool:
                # so i change by giving the full vector
                if values.shape[0] != nb_els:
                    raise IllegalAction(f"If provided with bool array, the number of components of the vector"
                                        f"should match the total number of {name_el}. You provided a vector "
                                        f"with size {values.shape[0]} and there are {nb_els} {name_el} "
                                        f"on the grid.")
                outer_vect[inner_vect[values]] = ~outer_vect[inner_vect[values]]
                return

            # this is the case where i give the integers i want to change
            try:
                values = values.astype(dt_int)
            except Exception as exc_:
                raise IllegalAction(f"{name_el}_id should be convertible to integer. Error was : \"{exc_}\"")
            if np.any(values < 0):
                raise IllegalAction(f"Impossible to change a negative {name_el} with negative id")
            if np.any(values > nb_els):
                raise IllegalAction(f"Impossible to change a {name_el} id because there are only "
                                    f"{nb_els} on the grid and you wanted to change an element with an "
                                    f"id > {nb_els} (in python id starts at 0)")
            outer_vect[inner_vect[values]] = ~outer_vect[inner_vect[values]]
            return
        elif isinstance(values, list):
            # 1 case only: list of int
            # (note: i cannot convert to numpy array other I could mix types...)
            for el_id_or_name in values:
                if isinstance(el_id_or_name, str):
                    tmp = np.where(name_els == el_id_or_name)[0]
                    if len(tmp) == 0:
                        raise IllegalAction(f"No known {name_el} with name \"{el_id_or_name}\"")
                    el_id = tmp[0]
                elif isinstance(el_id_or_name, (bool, dt_bool)):
                    # somehow python considers bool are int...
                    raise IllegalAction(f"If a list is provided, it is only valid with integer found "
                                        f"{type(el_id_or_name)}.")
                elif isinstance(el_id_or_name, (int, dt_int, np.int64)):
                    el_id = el_id_or_name
                else:
                    raise IllegalAction(f"If a list is provided, it is only valid with integer found "
                                        f"{type(el_id_or_name)}.")
                el_id = int(el_id)
                self._aux_affect_object_bool(el_id, name_el, nb_els, name_els,
                                             inner_vect=inner_vect, outer_vect=outer_vect)
        elif isinstance(values, set):
            # 2 cases: either set of load_id or set of load_name
            values = list(values)
            self._aux_affect_object_bool(values, name_el, nb_els, name_els,
                                         inner_vect=inner_vect, outer_vect=outer_vect)
        else:
            raise IllegalAction(f"Impossible to modify the {name_el} with inputs {values}. "
                                f"Please see the documentation.")

    @property
    def change_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which any element is **change**.

        It behaves similarly as :attr:`BaseAction.gen_change_bus` and can be use to modify any elements type
        as opposed to the more specific :attr:`BaseAction.gen_change_bus`, :attr:`BaseAction.load_change_bus`,
        :attr:`BaseAction.line_or_change_bus`, :attr:`BaseAction.line_ex_change_bus` or
        :attr:`BaseAction.storage_change_bus` that are specific to a certain type of objects.

        Notes
        -----

        For performance reasons, it do not allow to modify the elements by there names.

        The order of each elements are given in the :attr:`grid2op.Space.GridObjects.gen_pos_topo_vect`,
        :attr:`grid2op.Space.GridObjects.load_pos_topo_vect`,
        :attr:`grid2op.Space.GridObjects.line_or_pos_topo_vect`,
        :attr:`grid2op.Space.GridObjects.line_ex_pos_topo_vect` or
        :attr:`grid2op.Space.GridObjects.storage_pos_topo_vect`

        For example:

        .. code-block:: python

            act.set_bus [0, 1, 3]

        Will:

          * change the bus of the (unique) element for which \*_pos_topo_vect is 1
          * change the bus of (unique) element for which \*_pos_topo_vect is 2
          * change the bus of (unique) element for which \*_pos_topo_vect is 3

        You can use the documentation page :ref:`modeled-elements-module` for more information about which
        element correspond to what component of this "vector".

        """
        res = copy.deepcopy(self._change_bus_vect)
        res.flags.writeable = False
        return res

    @change_bus.setter
    def change_bus(self, values):
        orig_ = self.change_bus
        try:
            self._aux_affect_object_bool(values, "", self.dim_topo, None,
                                         np.arange(self.dim_topo), self._change_bus_vect)
            self._modif_change_bus = True
        except Exception as exc_:
            self._aux_affect_object_bool(orig_, "", self.dim_topo, None,
                                         np.arange(self.dim_topo), self._change_bus_vect)
            raise IllegalAction(f"Impossible to modify the bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def load_change_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the loads is **changed**.

        It behaves similarly as :attr:`BaseAction.gen_change_bus`. See the help there for more information.
        """
        res = self.change_bus[self.load_pos_topo_vect]
        res.flags.writeable = False
        return res

    @load_change_bus.setter
    def load_change_bus(self, values):
        if "change_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the load bus (with \"change\") with this action type.")
        orig_ = self.load_change_bus
        try:
            self._aux_affect_object_bool(values, "load", self.n_load, self.name_load,
                                         self.load_pos_topo_vect, self._change_bus_vect)
            self._modif_change_bus = True
        except Exception as exc_:
            self._change_bus_vect[self.load_pos_topo_vect] = orig_
            raise IllegalAction(f"Impossible to modify the load bus with your input. Please consult the documentation. "
                                f"The error was \"{exc_}\"")

    @property
    def gen_change_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the action **change** the generator units.

        Returns
        -------
        res:
            A vector of bool, of size `act.n_gen` indicating what type of action is performed for
            each generator units with the convention :

            * ``False`` this generator is not affected by any "change" action
            * ``True`` this generator bus is not affected by any "change" action. If it was
              on bus 1, it will be moved to bus 2, if it was on bus 2 it will be moved to bus 1 (
              and if it was disconnected it will stay disconnected)

        Examples
        --------

        To retrieve the impact of the action on the storage unit, you can do:

        .. code-block:: python

            gen_buses = act.gen_change_bus

        To modify these buses you can do:

        .. code-block:: python

            # create an environment where i can modify everything
            import numpy as np
            import grid2op
            from grid2op.Action import CompleteAction
            env = grid2op.make("educ_case14_storage", test=True, action_class=CompleteAction)

            # create an action
            act = env.action_space()

            # method 1 : provide the full vector
            act.gen_change_bus = np.ones(act.n_gen, dtype=bool)

            # method 2: provide the index of the unit you want to modify
            act.gen_change_bus = 1

            # method 3: provide a list of the units you want to modify
            act.gen_change_bus = [1, 2]

            # method 4: change the storage unit by their name with a set
            act.gen_change_bus = {"gen_1_0"}

        .. note:: The "rule of thumb" to modify an object using "change" method it to provide always
            the ID of an object. The ID should be an integer (or a name in some cases). It does not
            make any sense to provide a "value" associated to an ID: either you change it, or not.

        Notes
        -----
        It is a "property", you don't have to use parenthesis to access it:

        .. code-block:: python

            # valid code
            gen_buses = act.gen_change_bus

            # invalid code, it will crash, do not run
            gen_buses = act.gen_change_bus()
            # end do not run

        And neither should you uses parenthesis to modify it:

        .. code-block:: python

            # valid code
            act.gen_change_bus = [1, 2, 3]

            # invalid code, it will crash, do not run
            act.gen_change_bus([1, 2, 3])
            # end do not run

        Property cannot be set "directly", you have to use the `act.XXX = ..` syntax. For example:

        .. code-block:: python

            # valid code
            act.gen_change_bus = [1, 3, 4]

            # invalid code, it will raise an error, and even if it did not it would have not effect
            # do not run
            act.gen_change_bus[1] = True
            # end do not run

        .. note:: Be careful not to mix "change" and "set". For "change" you only need to provide the ID of the elements
            you want to change, for "set" you need to provide the ID **AND** where you want to set them.

        """
        res = self.change_bus[self.gen_pos_topo_vect]
        res.flags.writeable = False
        return res

    @gen_change_bus.setter
    def gen_change_bus(self, values):
        if "change_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the gen bus (with \"change\") with this action type.")
        orig_ = self.gen_change_bus
        try:
            self._aux_affect_object_bool(values, "gen", self.n_gen, self.name_gen,
                                         self.gen_pos_topo_vect, self._change_bus_vect)
            self._modif_change_bus = True
        except Exception as exc_:
            self._change_bus_vect[self.gen_pos_topo_vect] = orig_
            raise IllegalAction(f"Impossible to modify the gen bus with your input. Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def storage_change_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the storage units are **changed**.

        It behaves similarly as :attr:`BaseAction.gen_change_bus`. See the help there for more information.
        """
        res = self.change_bus[self.storage_pos_topo_vect]
        res.flags.writeable = False
        return res

    @storage_change_bus.setter
    def storage_change_bus(self, values):
        if "change_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the storage bus (with \"change\") with this action type.")
        if "set_storage" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the storage units with this action type.")
        orig_ = self.storage_change_bus
        try:
            self._aux_affect_object_bool(values, "storage", self.n_storage, self.name_storage,
                                         self.storage_pos_topo_vect, self._change_bus_vect)
            self._modif_change_bus = True
        except Exception as exc_:
            self._change_bus_vect[self.storage_pos_topo_vect] = orig_
            raise IllegalAction(f"Impossible to modify the storage bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def line_or_change_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the origin side of powerlines are **changed**.

        It behaves similarly as :attr:`BaseAction.gen_change_bus`. See the help there for more information.
        """
        res = self.change_bus[self.line_or_pos_topo_vect]
        res.flags.writeable = False
        return res

    @line_or_change_bus.setter
    def line_or_change_bus(self, values):
        if "change_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the line (origin) bus (with \"change\") with this action type.")
        orig_ = self.line_or_change_bus
        try:
            self._aux_affect_object_bool(values, self._line_or_str, self.n_line, self.name_line,
                                         self.line_or_pos_topo_vect, self._change_bus_vect)
            self._modif_change_bus = True
        except Exception as exc_:
            self._change_bus_vect[self.line_or_pos_topo_vect] = orig_
            raise IllegalAction(f"Impossible to modify the line origin bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def line_ex_change_bus(self):
        """
        Allows to retrieve (and affect) the busbars at which the extremity side of powerlines are **changed**.

        It behaves similarly as :attr:`BaseAction.gen_change_bus`. See the help there for more information.
        """
        res = self.change_bus[self.line_ex_pos_topo_vect]
        res.flags.writeable = False
        return res

    @line_ex_change_bus.setter
    def line_ex_change_bus(self, values):
        if "change_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the line (ex) bus (with \"change\") with this action type.")
        orig_ = self.line_ex_change_bus
        try:
            self._aux_affect_object_bool(values, self._line_ex_str, self.n_line, self.name_line,
                                         self.line_ex_pos_topo_vect, self._change_bus_vect)
            self._modif_change_bus = True
        except Exception as exc_:
            self._change_bus_vect[self.line_ex_pos_topo_vect] = orig_
            raise IllegalAction(f"Impossible to modify the line extrmity bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def line_change_status(self):
        """
        Property to set the status of the powerline.

        It behave similarly than :attr:`BaseAction.gen_change_bus` but with the following convention:

        * ``False`` will not affect the powerline
        * ``True`` will change the status of the powerline. If it was connected, it will attempt to
          disconnect it, if it was disconnected, it will attempt to reconnect it.

        """
        res = copy.deepcopy(self._switch_line_status)
        res.flags.writeable = False
        return res

    @line_change_status.setter
    def line_change_status(self, values):
        if "change_line_status" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the status of powerlines (with \"change\") with this action type.")
        orig_ = 1 * self._switch_line_status
        try:
            self._aux_affect_object_bool(values, "line status", self.n_line, self.name_line,
                                         np.arange(self.n_line), self._switch_line_status)
            self._modif_change_status = True
        except Exception as exc_:
            self._switch_line_status[:] = orig_
            raise IllegalAction(f"Impossible to modify the line status with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    def _aux_affect_object_float(self, values, name_el, nb_els,
                                 name_els,
                                 inner_vect,
                                 outer_vect,
                                 ):
        """
        INTERNAL USE ONLY

        .. warning:: /!\\\\ Internal, do not use unless you know what you are doing /!\\\\

        NB : this do not set the _modif_set_bus attribute. It is expected to be set in the property setter.
        This is not set here, because it's recursive and if it fails at a point, it would be set for nothing

        values: the new values to set
        name_el: "load"
        nb_els: self.n_load
        inner_vect: self.load_pos_topo_vect
        name_els: self.name_load
        outer_vect: self._set_topo_vect

        will modify outer_vect[inner_vect]
        """
        if isinstance(values, (bool, dt_bool)):
            raise IllegalAction(f"Impossible to set {name_el} values with a single boolean.")
        elif isinstance(values, (int, dt_int, np.int64)):
            raise IllegalAction(f"Impossible to set {name_el} values with a single integer.")
        elif isinstance(values, (float, dt_float, np.float64)):
            raise IllegalAction(f"Impossible to set {name_el} values with a single float.")
        elif isinstance(values, tuple):
            # i provide a tuple: load_id, new_vals
            if len(values) != 2:
                raise IllegalAction(f"when set with tuple, this tuple should have size 2 and be: {name_el}_id, new_bus "
                                    f"eg. (3, 0.0)")
            el_id, new_val = values
            if isinstance(new_val, (bool, dt_bool)):
                raise IllegalAction(f"new_val should be a float. A boolean was provided")

            try:
                new_val = float(new_val)
            except Exception as exc_:
                raise IllegalAction(f"new_val should be convertible to a float. Error was : \"{exc_}\"")

            if isinstance(el_id, (float, dt_float, np.float64)):
                raise IllegalAction(f"{name_el}_id should be integers you provided float!")
            if isinstance(el_id, (bool, dt_bool)):
                raise IllegalAction(f"{name_el}_id should be integers you provided bool!")
            if isinstance(el_id, str):
                raise IllegalAction(f"{name_el}_id should be integers you provided string "
                                    f"(hint: you can use a dictionary to set the bus by name eg. "
                                    f"act.{name_el}_set_bus = {{act.name_{name_el}[0] : 1, act.name_{name_el}[1] : "
                                    f"0.0}} )!")

            try:
                el_id = int(el_id)
            except Exception as exc_:
                raise IllegalAction(f"{name_el}_id should be convertible to integer. Error was : \"{exc_}\"")
            if el_id < 0:
                raise IllegalAction(f"Impossible to set the bus of a {name_el} with negative id")
            if el_id >= nb_els:
                raise IllegalAction(f"Impossible to set a {name_el} id {el_id} because there are only "
                                    f"{nb_els} on the grid (and in python id starts at 0)")
            if np.isfinite(new_val):
                outer_vect[inner_vect[el_id]] = new_val
            return
        elif isinstance(values, np.ndarray):
            if isinstance(values.dtype, int) or values.dtype == dt_int or values.dtype == np.int64:
                # for this the user explicitly casted it as integer, this won't work.
                raise IllegalAction(f"{name_el}_id should be floats you provided int!")

            if isinstance(values.dtype, bool) or values.dtype == dt_bool:
                raise IllegalAction(f"{name_el}_id should be floats you provided boolean!")
            try:
                values = values.astype(dt_float)
            except Exception as exc_:
                raise IllegalAction(f"{name_el}_id should be convertible to float. Error was : \"{exc_}\"")
            indx_ok = np.isfinite(values)
            outer_vect[inner_vect[indx_ok]] = values[indx_ok]
            return
        elif isinstance(values, list):
            # 2 cases: list of tuple, or list (convertible to numpy array)
            if len(values) == nb_els:
                # 2 cases: either i set all loads in the form [(0,..), (1,..), (2,...)]
                # or i should have converted the list to np array
                if isinstance(values, (bool, dt_bool)):
                    raise IllegalAction(f"Impossible to set {name_el} values with a single boolean.")
                elif isinstance(values, (int, dt_int, np.int64)):
                    raise IllegalAction(f"Impossible to set {name_el} values with a single integer.")
                elif isinstance(values, (float, dt_float, np.float64)):
                    raise IllegalAction(f"Impossible to set {name_el} values with a single float.")
                elif isinstance(values[0], tuple):
                    # list of tuple, handled below
                    # TODO can be somewhat "hacked" if the type of the object on the list is not always the same
                    pass
                else:
                    # get back to case where it's a full vector
                    values = np.array(values)
                    self._aux_affect_object_float(values, name_el, nb_els, name_els,
                                                  inner_vect=inner_vect, outer_vect=outer_vect)
                    return

            # expected list of tuple, each tuple is a pair with load_id, new_vals: example: [(0, -1.0), (2,2.7)]
            for el in values:
                if len(el) != 2:
                    raise IllegalAction(f"If input is a list, it should be a  list of pair (el_id, new_val) "
                                        f"eg. [(0, 1.0), (2, 2.7)]")
                el_id, new_val = el
                if isinstance(el_id, str):
                    tmp = np.where(name_els == el_id)[0]
                    if len(tmp) == 0:
                        raise IllegalAction(f"No known {name_el} with name {el_id}")
                    el_id = tmp[0]
                self._aux_affect_object_float((el_id, new_val), name_el, nb_els, name_els,
                                              inner_vect=inner_vect, outer_vect=outer_vect)
        elif isinstance(values, dict):
            # 2 cases: either key = load_id and value = new_bus or key = load_name and value = new bus
            for key, new_val in values.items():
                if isinstance(key, str):
                    tmp = np.where(name_els == key)[0]
                    if len(tmp) == 0:
                        raise IllegalAction(f"No known {name_el} with name {key}")
                    key = tmp[0]
                self._aux_affect_object_float((key, new_val), name_el, nb_els, name_els,
                                              inner_vect=inner_vect, outer_vect=outer_vect)
        else:
            raise IllegalAction(f"Impossible to modify the {name_el} with inputs {values}. "
                                f"Please see the documentation.")

    @property
    def redispatch(self):
        """
        Allows to retrieve (and affect) the redispatching setpoint of the generators.

        Returns
        -------
        res:
            A vector of integer, of size `act.n_gen` indicating what type of action is performed for
            each generator units. Note that these are the setpoint. The actual redispatching that will
            be available might be different. See :ref:`generator-mod-el` for more information.

        Examples
        --------

        To retrieve the impact of the action on the storage unit, you can do:

        .. code-block:: python

            redisp = act.redispatch

        For each generator it will give the amount of redispatch this action wants to perform.

        To change the setpoint of the redispatching, you can do:

        .. code-block:: python

            # create an environment where i can modify everything
            import numpy as np
            import grid2op
            from grid2op.Action import CompleteAction
            env = grid2op.make("educ_case14_storage", test=True, action_class=CompleteAction)

            # create an action
            act = env.action_space()

            # method 1 : provide the full vector
            act.redispatch = np.ones(act.n_gen, dtype=float)  # only floats are accepted !

            # method 2: provide the index of the unit you want to modify
            act.redispatch = (1, 2.5)

            # method 3: provide a list of the units you want to modify
            act.redispatch = [(1, 2.5), (0, -1.3)]

            # method 4: change the storage unit by their name with a dictionary
            act.redispatch = {"gen_1_0": 2.0}

        .. note:: The "rule of thumb" to perform redispatching is to provide always
            the ID of an object AND its value. The ID should be an integer (or a name in some cases)
            and the value a float representing what amount of redispatching you want to perform on the
            unit with the associated ID.

        Notes
        -----
        It is a "property", you don't have to use parenthesis to access it:

        .. code-block:: python

            # valid code
            redisp = act.redispatch

            # invalid code, it will crash, do not run
            redisp = act.redispatch()
            # end do not run

        And neither should you uses parenthesis to modify it:

        .. code-block:: python

            # valid code
            act.redispatch = [(1, 2.5), (0, -1.3)]

            # invalid code, it will crash, do not run
            act.redispatch([(1, 2.5), (0, -1.3)])
            # end do not run

        Property cannot be set "directly", you have to use the `act.XXX = ..` syntax. For example:

        .. code-block:: python

            # valid code
            act.redispatch = [(1, 2.5), (0, -1.3)]

            # invalid code, it will raise an error, and even if it did not it would have not effect
            # do not run
            act.redispatch[1] = 2.5
            # end do not run

        .. note:: Be careful not to mix action to set something on a bus bar (where the values are integer,
            like "set_bus" or "set_status")
            and continuous action (where the values are float, like "redispatch" or "storage_p")

        """
        res = 1.0 * self._redispatch
        res.flags.writeable = False
        return res

    @redispatch.setter
    def redispatch(self, values):
        if "redispatch" not in self.authorized_keys:
            raise IllegalAction("Impossible to perform redispatching with this action type.")
        orig_ = self.redispatch
        try:
            self._aux_affect_object_float(values, "redispatching", self.n_gen, self.name_gen,
                                          np.arange(self.n_gen), self._redispatch)
            self._modif_redispatch = True
        except Exception as exc_:
            self._redispatch[:] = orig_
            raise IllegalAction(f"Impossible to modify the redispatching with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    @property
    def storage_p(self):
        """
        Allows to modify the setpoint of the storage units.

        It behaves similarly as :attr:`BaseAction.redispatch`. See the help there for more information.

        Notes
        ------
        The "load convention" is used for storage units. This means that:

        - if you ask a positive value, the storage unit will charge, power will be "taken" from the
          grid to the unit. The unit in this case will behave like a *load*
        - if you ask a negative value, the storage unit will discharge, power will be injected from
          the unit to the grid. The unit, in this case, will behave like a *generator*.

        For more information, feel free to consult the documentation :ref:`storage-mod-el` where more
        details are given about the modeling ot these storage units.
        """
        res = 1.0 * self._storage_power
        res.flags.writeable = False
        return res

    @storage_p.setter
    def storage_p(self, values):
        if "set_storage" not in self.authorized_keys:
            raise IllegalAction("Impossible to perform storage action with this action type.")
        if self.n_storage == 0:
            raise IllegalAction("Impossible to perform storage action with this grid (no storage unit"
                                "available)")
        orig_ = self.storage_p
        try:
            self._aux_affect_object_float(values, "storage", self.n_storage, self.name_storage,
                                          np.arange(self.n_storage), self._storage_power)
            self._modif_storage = True
        except Exception as exc_:
            self._storage_power[:] = orig_
            raise IllegalAction(f"Impossible to modify the storage active power with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    def _aux_aux_convert_and_check_np_array(self, array_):
        try:
            array_ = np.array(array_)
        except Exception as exc_:
            raise IllegalAction(f"When setting the topology by substation and by giving a tuple, the "
                                f"second element of the tuple should be convertible to a numpy "
                                f"array of type int. Error was: \"{exc_}\"")
        if isinstance(array_.dtype, (bool, dt_bool)) or array_.dtype == dt_bool or array_.dtype == bool:
            raise IllegalAction("To set substation topology, you need a vector of integers, and not a vector "
                                "of bool.")
        elif isinstance(array_.dtype, (float, dt_float)) or array_.dtype == dt_float or array_.dtype == float:
            raise IllegalAction("To set substation topology, you need a vector of integers, and not a vector "
                                "of float.")
        array_ = array_.astype(dt_int)
        if np.any(array_ < -1):
            raise IllegalAction(f"Impossible to set element to bus {np.min(array_)}. Buses must be "
                                f"-1, 0, 1 or 2.")
        if np.any(array_ > 2):
            raise IllegalAction(f"Impossible to set element to bus {np.max(array_)}. Buses must be "
                                f"-1, 0, 1 or 2.")
        return array_

    def _aux_set_bus_sub(self, values):
        if isinstance(values, (bool, dt_bool)):
            raise IllegalAction("Impossible to modify bus by substation with a single bool.")
        elif isinstance(values, (int, dt_int, np.int64)):
            raise IllegalAction("Impossible to modify bus by substation with a single integer.")
        elif isinstance(values, (float, dt_float, np.float64)):
            raise IllegalAction("Impossible to modify bus by substation with a single float.")
        elif isinstance(values, np.ndarray):
            # full topo vect
            if values.shape[0] != self.dim_topo:
                raise IllegalAction("Impossible to modify bus when providing a full topology vector "
                                    "that has not the right ")
            if values.dtype == dt_bool or values.dtype == bool:
                raise IllegalAction("When using a full vector for setting the topology, it should be "
                                    "of integer types")
            values = self._aux_aux_convert_and_check_np_array(values)
            self._set_topo_vect[:] = values
        elif isinstance(values, tuple):
            # should be a tuple (sub_id, new_topo)
            sub_id, topo_repr, nb_el = self._check_for_right_vectors_sub(values)
            topo_repr = self._aux_aux_convert_and_check_np_array(topo_repr)
            start_ = np.sum(self.sub_info[:sub_id])
            end_ = start_ + nb_el
            self._set_topo_vect[start_:end_] = topo_repr
        elif isinstance(values, list):
            if len(values) == self.dim_topo:
                # if list is the size of the full topo vect, it's a list representing it
                values = self._aux_aux_convert_and_check_np_array(values)
                self._aux_set_bus_sub(values)
                return
            # otherwise it should be a list of tuples: [(sub_id, topo), (sub_id, topo)]
            for el in values:
                if not isinstance(el, tuple):
                    raise IllegalAction("When provided a list, it should be a list of tuples: "
                                        "[(sub_id, topo), (sub_id, topo), ... ] ")
                self._aux_set_bus_sub(el)
        elif isinstance(values, dict):
            for sub_id, topo_repr in values.items():
                sub_id = self._aux_sub_when_dict_get_id(sub_id)
                self._aux_set_bus_sub((sub_id, topo_repr))
        else:
            raise IllegalAction("Impossible to set the topology by substation with your input."
                                "Please consult the documentation.")

    @property
    def sub_set_bus(self):
        # TODO doc
        res = 1 * self.set_bus
        res.flags.writeable = False
        return res

    @sub_set_bus.setter
    def sub_set_bus(self, values):
        if "set_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the substation bus (with \"set\") with this action type.")
        orig_ = self.sub_set_bus
        try:
            self._aux_set_bus_sub(values)
            self._modif_set_bus = True
        except Exception as exc_:
            self._set_topo_vect[:] = orig_
            raise IllegalAction(f"Impossible to modify the substation bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")

    def _aux_aux_convert_and_check_np_array_change(self, array_):
        try:
            array_ = np.array(array_)
        except Exception as exc_:
            raise IllegalAction(f"When setting the topology by substation and by giving a tuple, the "
                                f"second element of the tuple should be convertible to a numpy "
                                f"array of type int. Error was: \"{exc_}\"")
        if isinstance(array_.dtype, (int, dt_int)) or array_.dtype == dt_int or array_.dtype == int:
            raise IllegalAction("To change substation topology, you need a vector of bools, and not a vector "
                                "of int.")
        elif isinstance(array_.dtype, (float, dt_float)) or array_.dtype == dt_float or array_.dtype == float:
            raise IllegalAction("To change substation topology, you need a vector of bools, and not a vector "
                                "of float.")
        array_ = array_.astype(dt_bool)
        return array_

    def _check_for_right_vectors_sub(self, values):
        if len(values) != 2:
            raise IllegalAction("Impossible to set the topology of a substation with a tuple which "
                                "has not a size of 2 (substation_id, topology_representation)")
        sub_id, topo_repr = values
        if isinstance(sub_id, (bool, dt_bool)):
            raise IllegalAction("Substation id should be integer")
        if isinstance(sub_id, (float, dt_float, np.float64)):
            raise IllegalAction("Substation id should be integer")
        try:
            el_id = int(sub_id)
        except Exception as exc_:
            raise IllegalAction(f"Substation id should be convertible to integer. "
                                f"Error was \"{exc_}\"")
        try:
            size_ = len(topo_repr)
        except Exception as exc_:
            raise IllegalAction(f"Topology cannot be set with your input."
                                f"Error was \"{exc_}\"")
        nb_el = self.sub_info[el_id]
        if size_ != nb_el:
            raise IllegalAction(f"To set topology of a substation, you must provide the full list of the "
                                f"elements you want to modify. You provided a vector with {size_} components "
                                f"while there are {self.sub_info[el_id]} on the substation.")

        return sub_id, topo_repr, nb_el

    def _aux_change_bus_sub(self, values):
        if isinstance(values, (bool, dt_bool)):
            raise IllegalAction("Impossible to modify bus by substation with a single bool.")
        elif isinstance(values, (int, dt_int, np.int64)):
            raise IllegalAction("Impossible to modify bus by substation with a single integer.")
        elif isinstance(values, (float, dt_float, np.float64)):
            raise IllegalAction("Impossible to modify bus by substation with a single float.")
        elif isinstance(values, np.ndarray):
            # full topo vect
            if values.shape[0] != self.dim_topo:
                raise IllegalAction("Impossible to modify bus when providing a full topology vector "
                                    "that has not the right size.")
            if values.dtype == dt_int or values.dtype == int:
                raise IllegalAction("When using a full vector for setting the topology, it should be "
                                    "of bool types")
            values = self._aux_aux_convert_and_check_np_array_change(values)
            self._change_bus_vect[:] = values
        elif isinstance(values, tuple):
            # should be a tuple (sub_id, new_topo)
            sub_id, topo_repr, nb_el = self._check_for_right_vectors_sub(values)

            topo_repr = self._aux_aux_convert_and_check_np_array_change(topo_repr)
            start_ = np.sum(self.sub_info[:sub_id])
            end_ = start_ + nb_el
            self._change_bus_vect[start_:end_] = topo_repr
        elif isinstance(values, list):
            if len(values) == self.dim_topo:
                # if list is the size of the full topo vect, it's a list representing it
                values = self._aux_aux_convert_and_check_np_array_change(values)
                self._aux_change_bus_sub(values)
                return
            # otherwise it should be a list of tuples: [(sub_id, topo), (sub_id, topo)]
            for el in values:
                if not isinstance(el, tuple):
                    raise IllegalAction("When provided a list, it should be a list of tuples: "
                                        "[(sub_id, topo), (sub_id, topo), ... ] ")
                self._aux_change_bus_sub(el)
        elif isinstance(values, dict):
            for sub_id, topo_repr in values.items():
                sub_id = self._aux_sub_when_dict_get_id(sub_id)
                self._aux_change_bus_sub((sub_id, topo_repr))
        else:
            raise IllegalAction("Impossible to set the topology by substation with your input."
                                "Please consult the documentation.")

    def _aux_sub_when_dict_get_id(self, sub_id):
        if isinstance(sub_id, str):
            tmp = np.where(self.name_sub == sub_id)[0]
            if len(tmp) == 0:
                raise IllegalAction(f"No substation named {sub_id}")
            sub_id = tmp[0]
        elif not isinstance(sub_id, int):
            raise IllegalAction(f"When using a dictionary it should be either with key = name of the "
                                f"substation or key = id of the substation. You provided neither string nor"
                                f"int but {type(sub_id)}."
                                )
        return sub_id

    @property
    def sub_change_bus(self):
        res = copy.deepcopy(self.change_bus)
        res.flags.writeable = False
        return res

    @sub_change_bus.setter
    def sub_change_bus(self, values):
        if "change_bus" not in self.authorized_keys:
            raise IllegalAction("Impossible to modify the substation bus (with \"change\") with this action type.")
        orig_ = self.sub_change_bus
        try:
            self._aux_change_bus_sub(values)
            self._modif_change_bus = True
        except Exception as exc_:
            self._change_bus_vect[:] = orig_
            raise IllegalAction(f"Impossible to modify the substation bus with your input. "
                                f"Please consult the documentation. "
                                f"The error was:\n\"{exc_}\"")