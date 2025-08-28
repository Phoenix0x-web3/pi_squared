import asyncio
import random
from .http_client import BaseHttpClient
from loguru import logger
from data.settings import Settings


class QuestsClient(BaseHttpClient):
    BASE_LINK = "https://pisquared-api.pulsar.money/api/v1/"


    async def complete_quests(self, random_stop:bool = False):
        uncompleted_tasks = await self.get_uncompleted_tasks()
        random.shuffle(uncompleted_tasks)
        total_play, best_score = await self.get_game_stats()
        random_quest_complete = random.randint(1, len(uncompleted_tasks))
  
        for i, task in enumerate(uncompleted_tasks):
            task_id = task['id']
            task_title = task['title']
            
            if task.get('taskName') == 'quiz':
                arguments = task.get('arguments', [])
                correct_answer = None
                
                for arg in arguments:
                    if arg.get('name') == 'correctAnswer':
                        correct_answer = arg.get('value')
                        break
                
                if correct_answer:
                    task_result = await self.do_task_request(task_guid=task_id, extra_arguments=[correct_answer])
                    if task_result:
                        logger.success(f"{self.user} Completed quiz task {task_title} with answer: {correct_answer}")
                    else:
                        logger.error(f"{self.user} can't complete {task_title} with answer: {correct_answer}")
                else:
                    logger.debug(f"No correct answer found for quiz task {task_id}")
                    continue
                    
            elif task.get('taskName') == 'click_link':
                task_result = await self.do_task_request(task_guid=task_id)
                if task_result:
                    logger.success(f"{self.user} Completed click_link task {task_title}")
                else:
                    logger.error(f"{self.user} can't complete click_link task {task_title}")

            elif task.get('taskName') == 'pisquared_query':
                arguments = task.get('arguments', [])
                query_type = None
                min_value = None
                
                for arg in arguments:
                    if arg.get('name') == 'query':
                        query_type = arg.get('value')
                    if arg.get('name') == 'minValue':
                        min_value = int(arg.get('value')) 
                
                
                should_attempt_task = False
                if query_type == 'pisquared-games' and total_play >= min_value:
                    should_attempt_task = True
                elif query_type == 'pisquared-clicks' and best_score >= min_value:
                    should_attempt_task = True
                
                if should_attempt_task:
                    task_result = await self.do_task_request(task_guid=task_id, extra_arguments=[])
                    if task_result:
                        logger.success(f"{self.user} Completed game challenge task {task_title}")
                    else:
                        logger.error(f"{self.user} can't complete game challenge task {task_title}")
                else:
                    logger.debug(f"{self.user} does not meet conditions for game challenge task {task_title} (total_play: {total_play}, best_score: {best_score}, required: {min_value} for {query_type})")
                    continue
            else:
                continue
      
            if random_stop:
                if i > random_quest_complete:
                    logger.info(f"{self.user} complete {i} quests and random stop. Complete the rest after the games")
                    return True
            random_sleep = random.randint(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max)
            logger.debug(f"{self.user} {random_sleep} sleep seconds before next quest")
            await asyncio.sleep(random_sleep)
        
        logger.success(f"{self.user} completed or already completed all available quests")
        return True   


    async def do_task_request(self, task_guid: str, extra_arguments: list = []):
        json_data = {
            'taskGuid': task_guid,
            'extraArguments': extra_arguments
        }
        success, data = await self.request(url=f"{self.BASE_LINK}pulsar/challenges/do-task", method="POST", json_data=json_data, use_refresh_token=False)
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
        success, data = await self.request(url=f"{self.BASE_LINK}pulsar/challenges/pi-squared/tasks-status/1", method="GET", use_refresh_token=False)
        tasks_status = []
        if success and isinstance(data, dict):
            for task in data["tasksStatus"]:
                tasks_status.append(task)
        return tasks_status

    async def get_available_tasks(self):
        success, data = await self.request(url=f"{self.BASE_LINK}pulsar/challenges/pi-squared/1", method="GET",use_refresh_token=False)
        available_tasks = []
        if success and isinstance(data, dict):
            for task in data["tasks"]:
                if task["isEnabled"]:
                    available_tasks.append(task)
        return available_tasks
    
    async def get_game_stats(self,):
        session = await self.get_session()
        if not session:
            raise Exception("Can't get session")
        user_id = session["user"]["id"]
        success, data = await self.request(url=f"{self.BASE_LINK}game-statistics/user/{user_id}",method="GET", use_refresh_token=False)
        
        if not success:
            return 0, 0

        # New account / empty payload
        if not data:
            return 0, 0

        if isinstance(data, dict):
            total = int(data.get("totalGamesPlayed") or 0)
            best = int(data.get("bestScore") or 0)
            return total, best

 
        return 0, 0

    async def get_session(self):
        success, data = await self.request(url=f"{self.BASE_LINK}auth/session", method="GET")
        if success and isinstance(data,dict):
            return data
        return False
