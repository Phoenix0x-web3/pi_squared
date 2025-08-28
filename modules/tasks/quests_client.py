import asyncio
import random
from .http_client import BaseHttpClient
from loguru import logger
from data.settings import Settings


class QuestsClient(BaseHttpClient):
    
    async def complete_quiz_quests(self):
        uncompleted_tasks = await self.get_uncompleted_tasks()
        
        for task in uncompleted_tasks:
            if task.get('taskName') == 'quiz':
                task_id = task['id']
                task_title = task['title']
                arguments = task.get('arguments', [])
                correct_answer = None
                
                for arg in arguments:
                    if arg.get('name') == 'correctAnswer':
                        correct_answer = arg.get('value')
                        break
                
                if correct_answer:
                    task = await self.do_task_request(task_guid=task_id, extra_arguments=[correct_answer])
                    if task:
                        logger.success(f"{self.user} Completed quiz task {task_title} with answer: {correct_answer}")
                        random_sleep = random.randint(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max)
                        logger.info(f"{self.user} {random_sleep} sleep seconds before next quest")
                        await asyncio.sleep(random_sleep)
                    else:
                        logger.error(f"{self.user} can't complete {task_title} with answer: {correct_answer}")
                        random_sleep = random.randint(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max)
                        logger.info(f"{self.user} {random_sleep} sleep seconds before next quest")
                        await asyncio.sleep(random_sleep)
                else:
                    logger.debug(f"No correct answer found for quiz task {task_id}")
                    continue
        logger.success(f"{self.user} completed or already completed all quiz quests")
        return True


    async def do_task_request(self, task_guid: str, extra_arguments: list = []):
        json_data = {
            'taskGuid': task_guid,
            'extraArguments': extra_arguments
        }
        success, data = await self.request(url="https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/do-task", method="POST", json_data=json_data, use_refresh_token=False)
        logger.debug(data)
        if success and isinstance(data, dict) and data['status']:
            return True
        return False


    async def get_uncompleted_tasks(self):
        uncompleted_tasks = []
        available_tasks = await self.get_available_tasks()
        tasks_status = await self.get_tasks_status()
        count = 0
        for i in available_tasks:
            for a in tasks_status:
                if i['id'] == a["taskGuid"]:
                    count += 1
                    if a['status'] != "SUCCESSFUL":
                        uncompleted_tasks.append(i)
        return uncompleted_tasks

    async def get_tasks_status(self):
        success, data = await self.request(url="https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/pi-squared/tasks-status/1", method="GET", use_refresh_token=False)
        tasks_status = []
        if success and isinstance(data, dict):
            for task in data["tasksStatus"]:
                tasks_status.append(task)
        return tasks_status

    async def get_available_tasks(self):
        success, data = await self.request(url="https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/pi-squared/1", method="GET",use_refresh_token=False)
        available_tasks = []
        if success and isinstance(data, dict):
            for task in data["tasks"]:
                if task["isEnabled"]:
                    available_tasks.append(task)
        return available_tasks
