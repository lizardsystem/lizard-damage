import logging
from celery.task import task
from lizard_task.task import task_logging


@task
@task_logging
def damage_task(username=None, taskname=None, loglevel=20):
    logger = logging.getLogger(taskname)
    # Do your thing
    logger.info("Doing my thing")
