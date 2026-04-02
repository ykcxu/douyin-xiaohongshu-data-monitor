from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

from app.config.settings import get_settings
from app.services.login_state_service import LoginStateService


class BrowserLoginManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.login_state_service = LoginStateService()

    def state_file(self, platform: str, account_id: str) -> Path:
        return self.settings.browser_state_dir / platform / f"{account_id}.json"

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

    def interactive_login(self, platform: str, account_id: str, login_url: str) -> Path:
        with sync_playwright() as playwright:
            context = self.create_context(playwright, platform, account_id)
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded")
            page.wait_for_timeout(60000)
            state_file = self.save_state(context, platform, account_id)
            browser = context.browser
            context.close()
            if browser is not None:
                browser.close()
        self.login_state_service.upsert_storage_state(
            platform=platform,
            account_id=account_id,
            storage_state_path=state_file,
        )
        return state_file
