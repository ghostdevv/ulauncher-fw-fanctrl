import json
import subprocess
from typing import TypedDict, List
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from fuzzyfinder import fuzzyfinder


class State(TypedDict):
    active: bool
    strategy: str
    speed: int
    temperature: float
    strategies: List[str]


class FwFanctrlExtension(Extension):
    state: State | None = None

    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener(self))
        self.subscribe(ItemEnterEvent, ItemEnterEventListener(self))
        self.refresh_state()

    def handle_toggle_active_action(self, query: str | None):
        if self.state is None:
            return self.refresh_and_render(query)

        try:
            subprocess.run(
                ["fw-fanctrl", "pause" if self.state["active"] else "resume"],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            return self.render_error(str(e))

        return self.refresh_and_render(query)

    def handle_set_strategy_action(self, query: str | None, strategy: str):
        if self.state is None:
            return self.refresh_and_render(query)

        try:
            subprocess.run(["fw-fanctrl", "use", strategy], check=True)
        except subprocess.CalledProcessError as e:
            return self.render_error(str(e))

        return self.refresh_and_render(query)

    def refresh_state(self) -> str | None:
        try:
            result = subprocess.run(
                ["fw-fanctrl", "--output-format=JSON", "print", "all"],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)

            self.state = {
                "strategy": data["strategy"],
                "active": data["active"],
                "speed": data["speed"],
                "temperature": data["temperature"],
                "strategies": list(data["configuration"]["data"]["strategies"].keys()),
            }
            return None
        except subprocess.CalledProcessError as e:
            return f"fw-fanctrl command failed: {str(e)}"
        except json.JSONDecodeError as e:
            return f"Failed to parse fw-fanctrl output: {str(e)}"
        except FileNotFoundError:
            return "fw-fanctrl command not found. Please ensure it's installed and in PATH."

    def render_error(self, error: str):
        return RenderResultListAction(
            [
                ExtensionResultItem(
                    icon="images/fw-fanctrl.png",
                    name="An unexpected error occurred",
                    description="Press enter to copy to clipboard, good luck o7",
                    on_enter=CopyToClipboardAction(error),
                )
            ]
        )

    def refresh_and_render(self, query: str | None):
        error = self.refresh_state()
        if error:
            return self.render_error(error)

        return self.render(query)

    def render(self, query: str | None):
        if self.state is None:
            return self.refresh_and_render(query)

        all = [
            ExtensionResultItem(
                icon=f"images/{'active' if self.state['active'] else 'inactive'}.png",
                name="Running" if self.state["active"] else "Stopped",
                description=(
                    f'Temperature: {self.state["temperature"]}°C Fan Speed {self.state["speed"]}%'
                    if self.state["active"]
                    else "Your Framework will use its default fan behaviour"
                ),
                on_enter=ExtensionCustomAction(
                    {"action": "toggle-active", "query": query}, True
                ),
                keyword="stop" if self.state["active"] else "start",
            )
        ] + [
            ExtensionResultItem(
                icon=f"images/{'check' if strategy == self.state['strategy'] else 'empty'}.png",
                name=strategy.replace("-", " ").title(),
                on_enter=ExtensionCustomAction(
                    {"action": "set-strategy", "query": query, "strategy": strategy},
                    True,
                ),
                keyword=strategy,
            )
            for strategy in self.state["strategies"]
        ]

        if not query:
            return RenderResultListAction(all)

        items: list[ExtensionResultItem] = list(
            fuzzyfinder(
                query,
                all,
                accessor=lambda item: item.get_keyword(),
            )
        )

        return RenderResultListAction(items)


class KeywordQueryEventListener(EventListener):
    extension: FwFanctrlExtension

    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def on_event(self, event: KeywordQueryEvent, _):  # type: ignore
        return self.extension.render(event.get_argument())


class ItemEnterEventListener(EventListener):
    extension: FwFanctrlExtension

    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def on_event(self, event: ItemEnterEvent, _):  # type: ignore
        data = event.get_data()

        if data and data.get("action") == "toggle-active":
            return self.extension.handle_toggle_active_action(data.get("query"))
        elif data and data.get("action") == "set-strategy":
            return self.extension.handle_set_strategy_action(
                data.get("query"), data.get("strategy")
            )

        return DoNothingAction()


if __name__ == "__main__":
    FwFanctrlExtension().run()
