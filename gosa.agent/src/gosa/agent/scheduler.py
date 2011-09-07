# -*- coding: utf-8 -*-
"""
TODO: docs
"""
from zope.interface import implements
from gosa.common.handler import IInterfaceHandler
from gosa.common import Environment
from gosa.common.utils import N_
from gosa.common.components.scheduler import Scheduler, set_job_property
from gosa.common.components.scheduler.jobstores.sqlalchemy_store import SQLAlchemyJobStore
from gosa.common.components.scheduler.triggers import SimpleTrigger, IntervalTrigger, CronTrigger


class SchedulerService(object):
    """
    TODO: docs
    """
    implements(IInterfaceHandler)
    _priority_ = 0

    # Target queue
    _target_ = 'core'

    def __init__(self):
        env = Environment.getInstance()
        env.log.debug("initializing scheduler")
        self.env = env

        self.sched = Scheduler(origin=self.env.id)
        self.sched.add_jobstore(SQLAlchemyJobStore(
            engine=env.getDatabaseEngine('scheduler'),
            tablename='scheduler_jobs'), 'db')

    def serve(self):
        """
        Start the scheduler service.
        """
        self.sched.start()

        # Start migration job
        self.sched.add_interval_job(self.migrate, seconds=60)

        #TODO: add event listener for remote schedulers

    def stop(self):
        """ Stop scheduler service. """
        self.sched.shutdown()

    def migrate(self):
        """
        Migration "cron" job.
        """
        self.env.log.debug("scheduler: looking for stale jobs")
        #TODO: realy look for stale jobs
        #self.sched.reschedule()

    @Command(__help__=N_("Return scheduler information for a specific job."))
    def schedulerGetJob(self, job_id):
        return self.sched.get_job_by_id(job_id)

    @Command(__help__=N_("List jobs matchings an optional filter."))
    def schedulerGetJobs(self, fltr=None):
        res = {}

        for job in self.sched.get_jobs():
            job_dict = dict([(key, getattr(f, key)) for key in [
                'misfire_grace_time',
                'coalesce',
                'name',
                'max_runs',
                'max_instances',
                'tag',
                'owner',
                'description']])

            if fltr:
                hits = 0
                for key, value in fltr.items():
                    if getattr(job, key) == value:
                        hits += 1
                if hits == len(fltr):
                    res[job.uuid] = job_dict

            else:
                res[job.uuid] = job_dict

        return res

    @Command(needsUser=True, __help__=N_("Add a new date based job to the scheduler."))
    def schedulerAddDateJob(self, user, func, args, kwargs, date, **options):
        """
        Add a new job triggered at a specified date.

        =========== =======================================
        Parameter   Description
        =========== =======================================
        func        Function *pointer*
        args        Function arguments
        kwargs      Function keyword arguments
        date        Execution date of the function
        options     Set of job options
        =========== =======================================

        A job can have these options:

        =================== ===============================================================================
        Option              Description
        =================== ===============================================================================
        name                Job name
        description         Description of the job
        tag                 Free choosable text tag to make it easier to find jobs
        misfire_grace_time  seconds after the designated run time that the job is still allowed to be run
        coalesce            Roll several pending executions of jobs into one
        max_runs            Maximum number of times this job is allowed to be triggered
        max_instances       Maximum number of concurrently running instances allowed for this job
        callback            Function to be called after the job has been done
        =================== ===============================================================================

        `Return:` Job ID
        """
        options['owner'] = user
        trigger = SimpleTrigger(date)
        job = self.sched.add_job(trigger, func, args, kwargs, **options)
        return job.uuid

    @Command(needsUser=True, __help__=N_("Add a new cron based job to the scheduler."))
    def schedulerCronDateJob(self, user, func, args, kwargs, year=None, month=None,
            day=None, week=None, day_of_week=None, hour=None, minute=None, second=None,
            start_date=None, **options):
        """
        Add a new job triggered in a cron style manner.

        =========== =======================================
        Parameter   Description
        =========== =======================================
        func        Function *pointer*
        args        Function arguments
        kwargs      Function keyword arguments
        year        Year to run on
        month       Month to run on
        day         Day of month to run on
        week        Week of the year to run on
        day_of_week Weekday to run on (0 = Monday)
        hour        Hour to run on
        second      Second to run on
        options     Set of job options
        =========== =======================================

        For an option description, see :meth:`gosa.agent.scheduler.SchedulerService.schedulerDateJob`.

        `Return:` Job ID
        """
        options['owner'] = user
        trigger = CronTrigger(year=year, month=month, day=day, week=week,
                day_of_week=day_of_week, hour=hour,
                minute=minute, second=second,
                start_date=start_date)
        jod = self.sched.add_job(trigger, func, args, kwargs, **options)
        return job.uuid

    @Command(needsUser=True, __help__=N_("Add a new interval job to the scheduler."))
    def schedulerInterval(self, user, func, args, kwargs, weeks=0, days=0, hours=0,
            minutes=0, seconds=0, start_date=None, **options):
        """
        Add a new job triggered in a specified interval.

        =========== =======================================
        Parameter   Description
        =========== =======================================
        func        Function *pointer*
        args        Function arguments
        kwargs      Function keyword arguments
        weeks       Number of weeks to wait
        days        Number of days to wait
        hours       Number of hours to wait
        minutes     Number of minutes to wait
        seconds     Number of seconds to wait
        start_date  When to first execute the job
        options     Set of job options
        =========== =======================================

        For an option description, see :meth:`gosa.agent.scheduler.SchedulerService.schedulerDateJob`.

        `Return:` Job ID
        """
        options['owner'] = user
        interval = timedelta(weeks=weeks, days=days, hours=hours,
                minutes=minutes, seconds=seconds)
        trigger = IntervalTrigger(interval, start_date)
        job = self.sched.add_job(trigger, func, args, kwargs, **options)
        return job.uuid

    @Command(needsUser=True, __help__=N_("Add a new job to the scheduler."))
    def schedulerUpdateJob(self, user, job_id):
        pass

    @Command(needsUser=True, __help__=N_("Remove job from the scheduler."))
    def schedulerRemoveJob(self, user, job_id):
        pass
