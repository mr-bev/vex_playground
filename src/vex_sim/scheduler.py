"""Single-threaded cooperative scheduler for student programs.

The simulator's main loop drives student code step-by-step. When the
student calls a time-taking API method (``wait``, ``drive_for``,
``spin_for``, ...), that method *suspends* the student until simulated
time has advanced enough; the main loop resumes the student then. The
suspend/resume happens inside one OS thread, with one Python frame stack
active at a time. Pygame, the world, and sensor caches all live on that
same thread.

Why greenlet, not Python generators
-----------------------------------

The natural-looking design is "make ``wait`` a generator that ``yield``s
until its deadline". It does not work, and it is worth writing down
exactly why so a future maintainer doesn't try to "simplify" this module
back to ``yield`` and rediscover the issue:

* ``yield`` only suspends the function it appears in. It does not climb
  the call stack. If the student writes ``wait(50, MSEC)``, control is
  inside ``wait``; for ``yield`` inside ``wait`` to suspend the *student*,
  every frame between the student's top level and ``wait`` would have to
  be a generator, and every call site between them would need
  ``yield from``. Student source is plain synchronous Python.
* That implies AST-rewriting the student source to wrap every
  time-taking call in ``yield from`` and converting every transitively
  yielding student-defined helper into a generator. The set of helpers
  is dynamic (lambdas, comprehensions, methods on student classes,
  decorated functions, calls through aliases / locals), so the rewrite
  is an unbounded reflective transformation.
* Even when correct, generator-based code interacts awkwardly with
  pdb: stepping into a generator function shows the suspension
  machinery in the stack instead of the user's logical flow.

Greenlets sidestep the call-stack problem. A greenlet captures and
restores its *entire* C stack on each ``switch``, so suspending from
inside ``wait`` (or three levels deeper) returns control to whoever
launched the greenlet without touching any intermediate frame. The
student code stays synchronous, the API methods do the bookkeeping, and
the debugger sees one logical stack at a time.

We picked greenlet over threads for the reasons that prompted the
refactor: no locks, no GIL-release patterns affecting determinism, no
breakpoints crossing thread boundaries, pygame stays where it wants to
be. Greenlet is a long-standing C extension (used by SQLAlchemy, gevent,
eventlet) with prebuilt wheels on every platform we target.

How this module is used
-----------------------

* :data:`SCHEDULER` is a process-global singleton. The runner installs
  a student program with :meth:`_Scheduler.install`, then drives it via
  :meth:`_Scheduler.advance_to_next_wait` until done.
* API methods on the student-facing surface (``wait``, ``drive_for`` …)
  call :meth:`_Scheduler.yield_for` from inside the student greenlet.
  When called *outside* a student greenlet — e.g. from a unit test that
  exercises an API method directly — :meth:`yield_for` falls back to a
  plain :func:`SIM_CLOCK.advance`, preserving the synchronous,
  pre-scheduler behaviour the test fixtures rely on.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from greenlet import GreenletExit, greenlet

from vex_sim.api._clock import SIM_CLOCK


class _Scheduler:
    def __init__(self) -> None:
        self._main: greenlet | None = None
        self._student: greenlet | None = None
        self._student_fn: Callable[[], None] | None = None
        self._done: bool = True
        # The deadline (sim seconds) the student is currently suspended on,
        # or -inf if no wait is pending (student hasn't yielded yet, or has
        # finished). Carries the value passed to yield_for.
        self._pending_deadline: float = float("-inf")

    # ------------------------------------------------------------------
    # Lifecycle: install, kill
    # ------------------------------------------------------------------

    def install(self, student_fn: Callable[[], None]) -> None:
        """Prepare a student greenlet around ``student_fn``.

        The greenlet is *not* run yet — :meth:`advance_to_next_wait`
        starts it. Calling install while a previous student is still
        alive kills that one first.
        """
        self.kill()
        self._main = greenlet.getcurrent()
        self._student = greenlet(self._student_body)
        self._student_fn = student_fn
        self._done = False
        self._pending_deadline = float("-inf")

    def kill(self) -> None:
        """Tear down the current student greenlet, if any.

        Called by the runner in its ``finally`` block. Throws
        :class:`GreenletExit` into a still-suspended student so its
        ``finally`` clauses run; greenlets that have already finished
        are left to the GC.
        """
        if self._student is not None and not self._student.dead:
            with contextlib.suppress(GreenletExit):
                self._student.throw(GreenletExit)
        self._student = None
        self._main = None
        self._student_fn = None
        self._done = True
        self._pending_deadline = float("-inf")

    # ------------------------------------------------------------------
    # Called from inside the student greenlet
    # ------------------------------------------------------------------

    def in_student_context(self) -> bool:
        return self._student is not None and greenlet.getcurrent() is self._student

    def yield_for(self, deadline: float) -> None:
        """Suspend the student greenlet until SIM_CLOCK reaches ``deadline``.

        Called by API methods that take simulated time. When invoked
        outside a student greenlet (e.g. from a test harness), falls
        back to a synchronous SIM_CLOCK.advance so the API remains
        usable in non-scheduler contexts.
        """
        if self._main is None or not self.in_student_context():
            seconds = max(0.0, float(deadline) - SIM_CLOCK.now())
            SIM_CLOCK.advance(seconds)
            return
        if deadline <= SIM_CLOCK.now():
            # Wait already satisfied — no need to switch.
            return
        # Pass the deadline to main; main returns control here once the
        # clock has been advanced to (or past) deadline.
        self._main.switch(float(deadline))

    def _student_body(self) -> None:
        try:
            assert self._student_fn is not None
            self._student_fn()
        finally:
            # Whether the student returned normally or an exception is
            # propagating, this greenlet is finished. Greenlet re-raises
            # any propagating exception in main on the next switch, so the
            # runner sees it via the standard try/except path.
            self._done = True

    # ------------------------------------------------------------------
    # Called from the main greenlet (runner / render loop)
    # ------------------------------------------------------------------

    def advance_to_next_wait(self) -> bool:
        """Resume the student until it yields a wait or finishes.

        Returns True if the student yielded a new wait; ``pending_deadline``
        is updated. Returns False if the student finished. Any exception
        propagating out of the student greenlet is re-raised here.
        """
        if self._done or self._student is None:
            return False
        result = self._student.switch()
        if self._done:
            self._pending_deadline = float("-inf")
            return False
        # The student suspended via yield_for, which does main.switch(deadline).
        self._pending_deadline = float(result)
        return True

    @property
    def pending_deadline(self) -> float:
        return self._pending_deadline

    @property
    def done(self) -> bool:
        return self._done


SCHEDULER = _Scheduler()
