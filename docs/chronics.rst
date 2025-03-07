.. currentmodule:: grid2op.Chronics

Chronics
===================================

Objectives
-----------
This module is present to handle everything related to input data that are not structural.

In the Grid2Op vocabulary a "GridValue" or "Chronics" is something that provides data to change the input parameter
of a power flow between 1 time step and the other.

It is a more generic terminology. Modification that can be performed by :class:`GridValue` object includes, but
are not limited to:

  - injections such as:

    - generators active production setpoint
    - generators voltage setpoint
    - loads active consumption
    - loads reactive consumption

  - structural informations such as:

    - planned outage: powerline disconnection anticipated in advance
    - hazards: powerline disconnection that cannot be anticipated, for example due to a windstorm.

All powergrid modification that can be performed using an :class:`grid2op.Action.BaseAction` can be implemented as
form of a :class:`GridValue`.

The same mechanism than for :class:`grid2op.Action.BaseAction` or :class:`grid2op.Observation.BaseObservation`
is pursued here. All state modifications made by the :class:`grid2op.Environment` must derived from
the :class:`GridValue`. It is not recommended to create them directly, but rather to use
the :class:`ChronicsHandler` for such a purpose.

Note that the values returned by a :class:`GridValue` are **backend dependant**. A GridValue object should always
return the data in the order expected by the :class:`grid2op.Backend`, regardless of the order in which data are given
in the files or generated by the data generator process.

This implies that changing the backend will change the output of :class:`GridValue`. More information about this
is given in the description of the :func:`GridValue.initialize` method.

Finally, compared to other Reinforcement Learning problems, is the possibility to use "forecast". This optional feature
can be accessed via the :class:`grid2op.Observation.BaseObservation` and mainly the
:func:`grid2op.Observation.BaseObservation.simulate` method. The data that are used to generate this forecasts
come from the :class:`grid2op.GridValue` and are detailed in the
:func:`GridValue.forecasts` method.


More control on the chronics
-------------------------------
We explained, in the description of the :class:`grid2op.Environment` in sections
:ref:`environment-module-chronics-info` and following how to have more control on which chronics is used,
with steps are used within a chronics etc. We will not detailed here again, please refer to this page
for more information.

However, know that you can have a very detailed control on which chronics are used:

- use `env.set_id(THE_CHRONIC_ID)` (see :func:`grid2op.Environment.Environment.set_id`) to set the id of the
  chronics you want to use
- use `env.chronics_handler.set_filter(a_function)` (see :func:`grid2op.Chronics.GridValue.set_filter`)
  to only use certain chronics
- use `env.chronics_handler.sample_next_chronics(probas)`
  (see :func:`grid2op.Chronics.GridValue.sample_next_chronics`) to draw at random some chronics
- use `env.fast_forward_chronics(nb_time_steps)`
  (see :func:`grid2op.Environment.BaseEnv.fast_forward_chronics`) to skip initial number of steps
  of a given chronics
- use `env.chronics_handler.set_max_iter(nb_max_iter)`
  (see :func:`grid2op.Chronics.ChronicsHandler.set_max_iter`) to limit the number of steps within an episode

Chosing the right chronics can also lead to some large advantage in terms of computation time. This is
particularly true if you want to benefit the most from HPC for example. More detailed is given in the
:ref:`environment-module-data-pipeline` section. In summary:

- set the "chunk" size (amount of data read from the disk, instead of reading an entire scenarios, you read
  from the hard drive only a certain amount of data at a time, see
  :func:`grid2op.Chronics.ChronicsHandler.set_chunk_size`) you can use it with
  `env.chronics_handler.set_chunk_size(100)`
- cache all the chronics and use them from memory (instead of reading them from the hard drive, see
  :class:`grid2op.Chronics.MultifolderWithCache`) you can do this with
  `env = grid2op.make(..., chronics_class=MultifolderWithCache)`

Finally, if you need to study machine learning in a "regular" fashion, with a train / validation / set
you can use the `env.train_val_split` or `env.train_val_split_random` functions to do that. See
an example usage in the section :ref:`environment-module-train-val-test`.




Detailed Documentation by class
--------------------------------

.. automodule:: grid2op.Chronics
    :members:
    :autosummary:

.. include:: final.rst
