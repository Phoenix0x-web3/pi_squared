from .http_client import BaseHttpClient
from loguru import logger


class QuestsClient(BaseHttpClient):
    
    async def complete_quiz_quests(self):
        first_quest = "8d52a94f-48b5-4bf7-a630-203ddf290177"
        await self.do_task_request(task_guid=first_quest, extra_arguments=["No"])


    async def do_task_request(self, task_guid: str, extra_arguments: list | None = None):
        json_data = {
            'taskGuid': task_guid,
        }
        if extra_arguments:
            json_data['extraArguments'] = extra_arguments
        success, data = await self.request(url="https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/do-task", method="POST", json_data=json_data, use_refresh_token=False)
        logger.debug(data)
        if success and isinstance(data, dict) and data['status']:
            return True
        return False

