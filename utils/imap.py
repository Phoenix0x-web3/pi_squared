import asyncio
from imaplib import IMAP4_SSL, IMAP4
from bs4 import BeautifulSoup
from time import time
from loguru import logger
from email import message_from_bytes
from typing import Union, List

from data.settings import Settings

class MailTimedOut(Exception):
    """Custom exception for email timeout errors."""
    pass

class Mail:
    def __init__(self, mail_data: str):
        """Initialize Mail with login credentials if provided."""
        self.mail_data = mail_data
        self.authed = False
        self.imap = None
        self.fake_mail = None
        if "icloud" in mail_data:
            self.mail_login, self.mail_pass, self.fake_mail = mail_data.split(':')
        else:
            self.mail_login, self.mail_pass = mail_data.split(':', 1)
        try:
            self._login(only_check=True)
        except ValueError as e:
            logger.error(f"Invalid mail_data format: {e}")
            raise

    def _login(self, only_check: bool = False) -> None:
        """Attempt to log in to the IMAP server."""
        try:
            self.imap = IMAP4_SSL(Settings().imap_server, Settings().imap_port)
            self.imap.login(self.mail_login, self.mail_pass)
            self.authed = True
        except IMAP4.error as error:
            error_msg = error.args[0].decode() if isinstance(error.args[0], bytes) else str(error)
            if only_check:
                logger.error(f"Email login failed for {self.mail_login}: {error_msg}")
            else:
                raise Exception(f"Email login failed for {self.mail_login}: {error_msg}")

    async def find_mail(
        self,
        msg_from: Union[str, List[str]],
        subject: str | None = None,
        part_subject: str | None = None,
    ) -> BeautifulSoup:
        """Search for an email matching the criteria asynchronously."""
        if isinstance(msg_from, str):
            msg_from = [msg_from]

        self._login()  # Ensure logged in before searching
        start_time = time()
        first = True
        if not self.imap:
            raise Exception("IMAP connection not established")

        while time() < start_time + 180:
            try:
                await asyncio.sleep(5)
                _, mailbox_data = self.imap.select('INBOX')
                last_mail_id = mailbox_data[0]
                if isinstance(last_mail_id, int):
                    last_mail_id = last_mail_id.decode()

                if last_mail_id == "0":
                    msg = None
                else:
                    _, data = self.imap.fetch(last_mail_id, "(BODY.PEEK[])")
                    # _, data = self.imap.fetch(last_mail_id, "(RFC822)")
                    raw_email = data[0][1]
                    msg = message_from_bytes(raw_email)

                if (
                    msg and
                    msg["From"] in msg_from and
                    (not self.fake_mail or msg["To"] == self.fake_mail) and
                    (not subject or msg["Subject"] == subject) and
                    (not part_subject or part_subject in (msg["Subject"] or "")) 
                ):
                    return self._format_mail(msg)

                if first:
                    logger.info(f"Waiting for mail from {', '.join(msg_from)}")
                    first = False

            except Exception as e:
                logger.error(f"Error while fetching email: {e}")
                await asyncio.sleep(5)

        raise MailTimedOut(f"Timeout waiting for email from {', '.join(msg_from)}")

    def _format_mail(self, mail) -> BeautifulSoup:
        """Extract and parse HTML content from an email."""
        try:
            if not mail.is_multipart():
                payload = mail.get_payload(decode=True)
                charset = mail.get_content_charset() or 'utf-8'
                return BeautifulSoup(payload.decode(charset), 'html.parser')

            for part in mail.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'iso-8859-1'
                    return BeautifulSoup(payload.decode(charset), 'html.parser')

            raise ValueError("No HTML content found in email")
        except Exception as e:
            logger.error(f"Error formatting email: {e}")
            raise

    def __del__(self):
        """Ensure IMAP connection is closed."""
        if self.imap and self.authed:
            try:
                self.imap.logout()
            except Exception as e:
                logger.error(f"Error during IMAP logout: {e}")
