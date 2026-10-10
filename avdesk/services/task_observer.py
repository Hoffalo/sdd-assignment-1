"""Accepted request -> ClickUp task, attached through the same Observer as the seam."""
from avdesk.integrations.task_tracker import TaskDraft, TaskTracker
from avdesk.requests_domain.events import RequestObserver, StatusChanged
from avdesk.requests_domain.facade import RequestsFacade
from avdesk.requests_domain.models import Status


class TaskTrackerObserver(RequestObserver):
    def __init__(self, tracker: TaskTracker, requests: RequestsFacade):
        self._tracker = tracker
        self._requests = requests

    def on_status_changed(self, event: StatusChanged) -> None:
        if event.to_status != Status.ACCEPTED:
            return
        snapshot = event.snapshot
        draft = TaskDraft(
            name=f"[{snapshot.public_code}] {snapshot.title}",
            markdown=snapshot.summary_markdown,
            due_date=snapshot.needed_by,
            urgent=snapshot.rush,
        )
        url = self._tracker.create_task(draft)
        if url:
            self._requests.attach_task_url(snapshot.request_id, url)
