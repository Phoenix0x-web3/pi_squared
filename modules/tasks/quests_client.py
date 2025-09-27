import asyncio
import random
import re

from loguru import logger

from data.settings import Settings
from utils.db_api.wallet_api import mark_discord_as_bad, update_discord_connect, update_points_and_top
from utils.discord.discord import DiscordOAuth
from utils.twitter.twitter_client import TwitterClient, TwitterStatuses

from .http_client import BaseHttpClient


class QuestsClient(BaseHttpClient):
    __module__ = "PiPortal Quests"
    BASE_LINK = "https://pisquared-api.pulsar.money/api/v1/"

    async def complete_quests(self, random_stop: bool = False):
        uncompleted_tasks = await self.get_uncompleted_tasks()
        random.shuffle(uncompleted_tasks)
        total_play, best_score = await self.get_game_stats()
        random_quest_complete = random.randint(1, len(uncompleted_tasks))
        logger.debug(uncompleted_tasks)

        for i, task in enumerate(uncompleted_tasks):
            task_id = task["id"]
            task_title = task["title"]
            if not self.user.discord_connected and 60 >= random.randint(1, 100):
                await self.connect_discord()

            if task.get("taskName") == "quiz":
                arguments = task.get("arguments", [])
                correct_answer = None

                for arg in arguments:
                    if arg.get("name") == "correctAnswer":
                        correct_answer = arg.get("value")
                        break

                if correct_answer:
                    task_result = await self.do_task_request(task_guid=task_id, extra_arguments=[correct_answer])
                    if task_result:
                        logger.success(f"{self.user} | {self.__module__} | Completed quiz task {task_title} with answer: {correct_answer}")
                    else:
                        logger.error(f"{self.user} | {self.__module__} | can't complete {task_title} with answer: {correct_answer}")
                else:
                    logger.debug(f"No correct answer found for quiz task {task_id}")
                    continue

            elif task.get("taskName") == "click_link":
                task_result = await self.do_task_request(task_guid=task_id)
                if task_result:
                    logger.success(f"{self.user} | {self.__module__} | Completed click_link task {task_title}")
                else:
                    logger.error(f"{self.user} | {self.__module__} | can't complete click_link task {task_title}")

            elif task.get("taskName") == "twitter_username" and self.user.twitter_token and self.user.twitter_status == TwitterStatuses.ok:
                twitter_client = TwitterClient(user=self.user)
                init = await twitter_client.initialize()
                if not init:
                    logger.warning(f"{self.user} can't initialize twitter")
                    continue
                connect = await self.connect_twitter_to_portal(twitter_client=twitter_client)
                if not connect:
                    logger.warning(f"{self.user} can't connect twitter")
                    continue
                change_name = await self.change_twitter_name(twitter_client=twitter_client)
                if change_name:
                    task_result = await self.do_task_request(task_guid=task_id)
                    if task_result:
                        logger.success(f"{self.user} | {self.__module__} | Completed twitter username task {task_title}")
                        await asyncio.sleep(5)
                        await self.change_twitter_name(twitter_client=twitter_client, change_back=True)
                    else:
                        logger.error(f"{self.user} | {self.__module__} | can't complete twitter username task {task_title}")
                else:
                    logger.warning(f"{self.user} can't change twitter name. Skip task")
                    continue

            elif task.get("taskName") == "pisquared_query":
                arguments = task.get("arguments", [])
                query_type = None
                min_value = None

                for arg in arguments:
                    if arg.get("name") == "query":
                        query_type = arg.get("value")
                    if arg.get("name") == "minValue":
                        min_value = int(arg.get("value"))

                should_attempt_task = False
                if query_type == "pisquared-games" and total_play >= min_value:
                    should_attempt_task = True
                elif query_type == "pisquared-clicks" and best_score >= min_value:
                    should_attempt_task = True
                elif query_type == "pisquared-peak-tps":
                    should_attempt_task = True

                elif query_type == "pisquared-active-players":
                    should_attempt_task = True

                if should_attempt_task:
                    task_result = await self.do_task_request(task_guid=task_id, extra_arguments=[])
                    if task_result:
                        logger.success(f"{self.user} | {self.__module__} | Completed game challenge task {task_title}")
                    else:
                        logger.warning(
                            f"{self.user} | {self.__module__} | can't complete game challenge task {task_title}.Not ready, will try later"
                        )
                else:
                    logger.debug(
                        f"{self.user} | {self.__module__} | does not meet conditions for game challenge task {task_title} (total_play: {total_play}, best_score: {best_score}, required: {min_value} for {query_type})"
                    )
                    continue
            else:
                continue

            if random_stop:
                if i > random_quest_complete:
                    logger.info(f"{self.user} | {self.__module__} | complete {i} quests and random stop. Complete the rest after the games")
                    return True
            random_sleep = random.randint(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max)
            logger.debug(f"{self.user} | {self.__module__} | {random_sleep} sleep seconds before next quest")
            await asyncio.sleep(random_sleep)

        logger.success(f"{self.user} | {self.__module__} | completed or already completed all available quests")
        await self.get_and_update_points()
        return True

    async def get_and_update_points(self):
        success, data = await self.request(url="https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/pi-squared/me/1", method="GET")
        logger.debug(data)
        if success and isinstance(data, dict):
            points = int(float(data["totalPoints"]))
            rank = data["rank"]
            logger.success(f"{self.user} user have {points} points and {rank} Rank")
            return update_points_and_top(id=self.user.id, points=int(points), top=int(rank))
        return False

    async def do_task_request(self, task_guid: str, extra_arguments: list = []):
        json_data = {"taskGuid": task_guid, "extraArguments": extra_arguments}
        success, data = await self.request(
            url=f"{self.BASE_LINK}pulsar/challenges/do-task", method="POST", json_data=json_data, use_refresh_token=False
        )
        if success and isinstance(data, dict) and data["status"]:
            return True
        return False

    async def get_uncompleted_tasks(self):
        uncompleted_tasks = []
        available_tasks = await self.get_available_tasks()
        tasks_status = await self.get_tasks_status()
        count = 0
        for i in available_tasks:
            for a in tasks_status:
                if i["id"] == a["taskGuid"]:
                    count += 1
                    if a["status"] != "SUCCESSFUL":
                        uncompleted_tasks.append(i)
        return uncompleted_tasks

    async def get_tasks_status(self):
        success, data = await self.request(
            url=f"{self.BASE_LINK}pulsar/challenges/pi-squared/tasks-status/1", method="GET", use_refresh_token=False
        )
        tasks_status = []
        if success and isinstance(data, dict):
            for task in data["tasksStatus"]:
                tasks_status.append(task)
        return tasks_status

    async def get_available_tasks(self):
        success, data = await self.request(url=f"{self.BASE_LINK}pulsar/challenges/pi-squared/1", method="GET", use_refresh_token=False)
        available_tasks = []
        if success and isinstance(data, dict):
            for task in data["tasks"]:
                if task["isEnabled"]:
                    available_tasks.append(task)
        return available_tasks

    async def get_game_stats(
        self,
    ):
        session = await self.get_session()
        if not session:
            raise Exception(f"{self.__module__} | Can't get session")
        user_id = session["user"]["id"]
        success, data = await self.request(url=f"{self.BASE_LINK}game-statistics/user/{user_id}", method="GET", use_refresh_token=False)

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
        if success and isinstance(data, dict):
            return data
        return False

    async def change_twitter_name(self, twitter_client, change_back: bool = False):
        name_now = twitter_client.twitter_account.name
        if change_back:
            if "π²" not in name_now:
                logger.debug(f"{self.user} | {self.__module__} | twitter name already clean")
                return True
            result = re.sub(r"π²", "", name_now).strip()
            return await twitter_client.change_name(name=result)

        if "π²" in name_now:
            logger.debug(f"{self.user} | {self.__module__} | twitter name already changed")
            return True

        return await twitter_client.change_name(name=twitter_client.twitter_account.name + "π²")

    async def connect_twitter_to_portal(self, twitter_client):
        check_connect = await self.check_media_connect(media="twitter")
        if check_connect:
            logger.info(f"{self.user} already have connected twitter")
            return True
        if not self.user.twitter_token or self.user.twitter_status != "OK":
            logger.warning(f"{self.user} can't connect twitter. Not twitter token or twitter status not OK")
            return False
        link = await self.request_twitter_link()
        if not link:
            return False
        await twitter_client.connect_twitter_to_site_oauth2(twitter_auth_url=str(link))
        check_connect = await self.check_media_connect(media="twitter")
        if check_connect:
            logger.success(f"{self.user} success connect twitter to site")
            await asyncio.sleep(5)
            return True
        else:
            logger.warning(f"{self.user} can't connect twitter to site")
            return False

    async def check_media_connect(self, media: str):
        _, data = await self.request(url="https://pisquared-api.pulsar.money/api/v1/pulsar/social-pay/me", method="GET")
        if media == "twitter":
            return data["twitterMetadata"]
        else:
            return data["discordMetadata"]

    async def request_twitter_link(self):
        json_data = {
            "type": "register",
            "redirectUrl": "https://portal.pi2.network/quests",
        }
        _, data = await self.request(
            url="https://pisquared-api.pulsar.money/api/v1/pulsar/social-pay/register/twitter", method="POST", json_data=json_data
        )
        return data

    async def request_discord_link(self):
        _, data = await self.request(
            url="https://pisquared-api.pulsar.money/api/v1/pulsar/social-pay/register/discord?redirectUri=https://portal.pi2.network/quests",
            method="GET",
        )
        return data

    async def connect_discord(self):
        check_connect = await self.check_media_connect(media="discord")
        if check_connect:
            logger.debug(f"{self.user} already have connected discord")
            update_discord_connect(id=self.user.id)
            return True
        if not self.user.discord_token or self.user.discord_status != "OK":
            logger.debug(f"{self.user} can't connect discord. Not discord token or discord status not OK")
            return False
        link = await self.request_discord_link()
        if not link:
            return False

        discord = DiscordOAuth(wallet=self.user)
        try:
            oauth_url, _ = await discord.start_oauth2(oauth_url=str(link))
        except Exception:
            mark_discord_as_bad(id=self.user.id)
            return False
        _ = await self.browser.get(url=oauth_url)
        check_connect = await self.check_media_connect(media="discord")
        if check_connect:
            logger.success(f"{self.user} success connect discord to site")
            update_discord_connect(id=self.user.id)
            await asyncio.sleep(5)
            return True
        else:
            logger.warning(f"{self.user} can't connect discord to site")
            return False
