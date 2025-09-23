import json
import random
import time
import uuid

from curl_cffi import CurlMime
from faker import Faker

from libs.baseAsyncSession import FINGERPRINT_DEFAULT
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import set_fs_form_status
from utils.retry import async_retry


class HSFormStatus:
    GOOD = "GOOD"
    BAD = "BAD"


class HSForm:
    __module__ = "HSForm"

    BASE_LINK = "https://pisquared-api.pulsar.money/api/v1/"

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.mail_waiter = None
        self.session = Browser(wallet=wallet)

    def get_base_headers(self):
        return {
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://share-eu1.hsforms.com",
            "Pragma": "no-cache",
            "Referer": "https://share-eu1.hsforms.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "sec-ch-ua-mobile": "?0",
        }

    @async_retry()
    async def is_valid_email(self, email):
        url = "https://forms-eu1.hsforms.com/emailcheck/v1/json-ext?hs_static_app=forms-embed&hs_static_app_version=1.9861&X-HubSpot-Static-App-Info=forms-embed-1.9861&portalId=145965351&formId=984a6e3c-89ca-4136-8085-c69a38b419fa&includeFreemailSuggestions=true"

        params = {
            "hs_static_app": "forms-embed",
            "hs_static_app_version": "1.9861",
            "X-HubSpot-Static-App-Info": "forms-embed-1.9861",
            "portalId": "145965351",
            "formId": "984a6e3c-89ca-4136-8085-c69a38b419fa",
            "includeFreemailSuggestions": "true",
        }

        resp = await self.session.post(url=url, params=params, headers=self.get_base_headers(), data=email, timeout=90)

        resp.raise_for_status()
        try:
            data = resp.json()
            return data["success"]

        except Exception:
            return False

    @async_retry()
    async def fill_form(self):
        if HSFormStatus.GOOD == self.wallet.hs_form_status:
            return f"Success | fill_form | HS Form already filled"

        if "icloud" in self.wallet.email_data:
            mail_login, mail_pass, fake_mail = self.wallet.email_data.split(":")
        else:
            mail_login, mail_pass = self.wallet.email_data.split(":", 1)
            fake_mail = None

        email = fake_mail if fake_mail else mail_login

        if not await self.is_valid_email(email):
            set_fs_form_status(self.wallet.id, HSFormStatus.BAD)
            return f"Failed | fill_form | invalid email for HS Form: {email}"

        url = "https://forms-eu1.hsforms.com/submissions/v3/public/submit/formsnext/multipart/145965351/984a6e3c-89ca-4136-8085-c69a38b419fa/json?hs_static_app=forms-embed&hs_static_app_version=1.9861&X-HubSpot-Static-App-Info=forms-embed-1.9861"

        now = str(int(time.time() * 1000))

        hs_context = {
            "embedAtTimestamp": str(now),
            "formDefinitionUpdatedAt": "1758299369929",
            "lang": "en",
            "embedType": "REGULAR",
            "disableCookieSubmission": "true",
            "clonedFromForm": "8bad4bf4-f035-4299-8f8e-4e27ec63372d",
            "userAgent": FINGERPRINT_DEFAULT["headers"]["user-agent"],
            "pageTitle": "Form",
            "pageUrl": "https://share-eu1.hsforms.com/1mEpuPInKQTaAhcaaOLQZ-g2ewjl3",
            "isHubSpotCmsGeneratedPage": False,
            "hutk": "f5019c857b3de1c567e86211795cbe67",
            "__hsfp": 2365989773,
            "__hssc": f"251652889.2.{now}",
            "__hstc": f"251652889.f5019c857b3de1c567e86211795cbe67.{now}.{now}.{now}.1",
            "formTarget": "#form-target",
            "locale": "en",
            "timestamp": now,
            "originalEmbedContext": {
                "portalId": "145965351",
                "formId": "984a6e3c-89ca-4136-8085-c69a38b419fa",
                "region": "eu1",
                "target": "#form-target",
                "isBuilder": False,
                "isTestPage": False,
                "isPreview": False,
                "isMobileResponsive": True,
                "pageUrl": "https://share-eu1.hsforms.com/1mEpuPInKQTaAhcaaOLQZ-g2ewjl3",
                "__INTERNAL__CONTEXT": {"editorVersion": "1.0"},
            },
            "correlationId": str(uuid.uuid4()),  # dynamic UUID
            "renderedFieldsIds": ["firstname", "lastname", "email", "role"],
            "captchaStatus": "NOT_APPLICABLE",
            "emailResubscribeStatus": "NOT_APPLICABLE",
            "isInsideCrossOriginFrame": False,
            "source": "forms-embed-1.9861",
            "sourceName": "forms-embed",
            "sourceVersion": "1.9861",
            "sourceVersionMajor": "1",
            "sourceVersionMinor": "9861",
            "allPageIds": {},
            "_debug_embedLogLines": [],
        }

        mp = CurlMime()
        mp.addpart(name="hs_context", data=json.dumps(hs_context), content_type="application/json")

        fake = Faker()
        first_name = fake.first_name()
        last_name = fake.last_name()

        mp.addpart(name="firstname", data=first_name)
        mp.addpart(name="lastname", data=last_name)
        mp.addpart(name="email", data=email)
        mp.addpart(name="role", data=random.choice(["Researcher", "Developer", "Pi Squared Community Member", "Other"]))

        r = await self.session.post(url=url, multipart=mp, headers=self.get_base_headers(), timeout=90)

        r.raise_for_status()
        try:
            data = r.json()
            if data["accepted"]:
                set_fs_form_status(self.wallet.id, HSFormStatus.GOOD)
                return f"Success | fill_form | HS Form filled successfully"

            set_fs_form_status(self.wallet.id, HSFormStatus.BAD)
            return f"Failed | fill_form | HS Form not filled, response: {data}"
        except Exception:
            return json.loads(r.text or "{}")
