from __future__ import annotations

from tools.calendar_tools import CalendarGetTool
from tools.accounts_tools import AccountsListTool
from tools.drive_tools import DriveListTool
from tools.email_tools import EmailReadTool
from tools.file_tools import FileDeleteTool, FileReadTool, FileUpdateTool, FileWriteTool
from tools.google_account_tools import GoogleAccountAddTool
from tools.web_tools import WebSearchTool


TOOL_REGISTRY = {
    "file.read": FileReadTool(),
    "file.write": FileWriteTool(),
    "file.update": FileUpdateTool(),
    "file.delete": FileDeleteTool(),
    "web.search": WebSearchTool(),
    "email.read": EmailReadTool(),
    "drive.list": DriveListTool(),
    "calendar.get": CalendarGetTool(),
    "accounts.list": AccountsListTool(),
    "google.account.add": GoogleAccountAddTool(),
}

