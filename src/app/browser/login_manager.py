from __future__ import annotations

import hashlib
import json
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

from app.config.settings import get_settings
from app.services.login_state_service import LoginStateService


DEFAULT_LOGIN_URLS = {
    "douyin": "https://live.douyin.com/",
    "xiaohongshu": "https://www.xiaohongshu.com/",
}


class BrowserLoginManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.login_state_service = LoginStateService()

    def state_file(self, platform: str, account_id: str) -> Path:
        return self.settings.browser_state_dir / platform / f"{account_id}.json"

    def resolve_login_url(self, platform: str, login_url: str | None = None) -> str:
        if login_url:
            return login_url
        return DEFAULT_LOGIN_URLS.get(platform, "about:blank")

    def create_context(self, playwright: Playwright, platform: str, account_id: str) -> BrowserContext:
        state_file = self.state_file(platform, account_id)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        browser = playwright.chromium.launch(headless=False)
        if state_file.exists():
            return browser.new_context(storage_state=str(state_file))
        return browser.new_context()

    def save_state(self, context: BrowserContext, platform: str, account_id: str) -> Path:
        state_file = self.state_file(platform, account_id)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(state_file))
        return state_file

    def compute_cookie_hash(self, state_file: Path) -> str | None:
        if not state_file.exists():
            return None

        payload = json.loads(state_file.read_text(encoding="utf-8"))
        cookies = payload.get("cookies", [])
        cookie_source = "|".join(
            f"{item.get('name', '')}={item.get('value', '')}@{item.get('domain', '')}"
            for item in cookies
        )
        if not cookie_source:
            return None
        return hashlib.sha256(cookie_source.encode("utf-8")).hexdigest()

    def interactive_login(
        self,
        platform: str,
        account_id: str,
        login_url: str | None = None,
        *,
        operator: str | None = None,
    ) -> Path:
        resolved_login_url = self.resolve_login_url(platform, login_url)
        with sync_playwright() as playwright:
            context = self.create_context(playwright, platform, account_id)
            page = context.new_page()
            page.goto(resolved_login_url, wait_until="domcontentloaded")
            prompt = (
                f"[{platform}] Browser opened for account '{account_id}'. "
                "Complete login in the browser, then press Enter here to save storage_state..."
            )
            print(prompt)
            try:
                input()
            except EOFError:
                # Fall back to a short wait when stdin is unavailable.
                page.wait_for_timeout(30000)
            state_file = self.save_state(context, platform, account_id)
            cookie_hash = self.compute_cookie_hash(state_file)
            browser = context.browser
            context.close()
            if browser is not None:
                browser.close()
        self.login_state_service.upsert_storage_state(
            platform=platform,
            account_id=account_id,
            storage_state_path=state_file,
            cookie_hash=cookie_hash,
            operator=operator,
        )
        return state_file
