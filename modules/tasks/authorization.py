from .http_client import BaseHttpClient
from utils.imap import Mail, MailTimedOut
from utils.db_api.models import Wallet
from faker import Faker
from loguru import logger
from utils.retry import async_retry


class AuthClient(BaseHttpClient):
    __module__ = 'PiPortal'

    BASE_LINK = "https://pisquared-api.pulsar.money/api/v1/"
    def __init__(self, user: Wallet):
        super().__init__(user)
        self.wallet = user
        self.mail_waiter = None

    @async_retry()
    async def login(self):
        logger.info(f"{self.user} | {self.__module__ } | starting authorize")
        session = await self.get_session()
        if session:
            logger.success(f"{self.user} | {self.__module__ } | success authorize")
            return session
        self.mail_waiter = Mail(self.user)
        if not self.mail_waiter.authed:
            return False

        email_login = self.mail_waiter.mail_login 

        await self.request_email_code(email=email_login)
        code = await self.get_verification_code()
        data = await self.send_verify_code(email=email_login, code=code)
        if isinstance(data, dict) and data["isDefaultUsername"]:
            await self.change_username()
        session = await self.get_session()
        logger.success(f"{self.user} | {self.__module__ } | success authorize")
        return session

    async def get_session(self):
        if not self.user.bearer_token:
            return False
        success, data = await self.request(url=self.BASE_LINK + "auth/session", method="GET")
        if success and "user" in data:
            return data
        return False

    def remove_digits(self, text):
        return ''.join(char for char in text if char.isalpha())

    async def change_username(self):
        faker = Faker()
        username = self.remove_digits(faker.user_name())
        json_data = {
            'username': username
        }
        success, data = await self.request(url=self.BASE_LINK + "auth/username", method="POST", json_data=json_data)
        if success:
            logger.success(f"{self.user} | {self.__module__ } | success change username from default to {username}")
            return True
        return False


    async def request_email_code(self, email: str): 
        if self.mail_waiter.fake_mail:
            email = self.mail_waiter.fake_mail
            
        json_data = {
            'email': email,
        }
        success, data = await self.request(url=self.BASE_LINK + "auth/request-otp", method="POST", json_data=json_data)
        if success:
            logger.success(f"{self.user} | {self.__module__ } | success request email code")
            return True
        raise Exception(f"{self.__module__ } | Can't request verify code")

    async def send_verify_code(self, email:str, code:str):
        json_data = {
            'email': email,
            'code': code
        }
        success, data = await self.request(url=self.BASE_LINK + "auth/verify-otp", method="POST", json_data=json_data)
        if success:
            logger.success(f"{self.user} | {self.__module__ } | success send email code {code}")
            return data
        raise Exception(f"{self.user} {self.__module__ } | Can't send verify code {code}")

    async def get_verification_code(self):
        """Get verification code from email"""
        for attempt in range(2):
            try:
                mail_body = await self.mail_waiter.find_mail(
                    msg_from=["updates@pulsar.money"],
                    part_subject="Login Code - Pi Squared"
                )
                strong_tags = mail_body.find_all("strong")
                if len(strong_tags) >= 2:
                    return strong_tags[1].text.strip()
            except MailTimedOut:
                logger.error(f"{self.user} | {self.__module__ } | Waiting mail timed out, attempt {attempt + 1}/2")
                if attempt == 0:
                    await self.request_email_code(self.mail_waiter.mail_login)
                else:
                    raise Exception(f"{self.__module__ } | Can't get verify code from email")
        raise Exception(f"{self.__module__ } | Can't get verify code from email")
                
